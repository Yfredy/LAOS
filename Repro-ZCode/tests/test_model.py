"""ShoNet 模型测试（来源① Fig.1：CNN+BiGRU+MHSA 全架构）。"""
import numpy as np
import pytest

torch = pytest.importorskip("torch")

from repro.sho.model import ShoNet, predict_degrees, AngleDataset


def test_forward_shape():
    torch.manual_seed(0)
    m = ShoNet(n_mics=6)
    x = torch.randn(2, 12, 100, 128)
    y = m(x)
    assert y.shape == (2, 2)


def test_param_count_lightweight():
    m = ShoNet(n_mics=6)
    n = sum(p.numel() for p in m.parameters())
    assert n < 2_000_000                       # 128 维 GRU+MHSA，轻量


def test_variable_time_length():
    m = ShoNet(n_mics=6)
    m.eval()
    with torch.no_grad():
        y1 = m(torch.randn(1, 12, 50, 128))
        y2 = m(torch.randn(1, 12, 200, 128))
    assert y1.shape == (1, 2) and y2.shape == (1, 2)


def test_predict_degrees_range():
    torch.manual_seed(0)
    m = ShoNet(n_mics=6).eval()
    feats = np.random.default_rng(0).standard_normal((3, 12, 60, 128)).astype(np.float32)
    deg = predict_degrees(m, feats)
    assert deg.shape == (3,)
    assert np.all((deg >= 0) & (deg < 360))


def test_backward_flow():
    m = ShoNet(n_mics=6)
    x = torch.randn(2, 12, 60, 128)
    th = torch.tensor([0.5, 2.0])
    target = torch.stack([torch.cos(th), torch.sin(th)], -1)
    loss = torch.mean((m(x) - target) ** 2)
    loss.backward()
    grads = [p.grad for p in m.parameters() if p.grad is not None]
    assert len(grads) > 0 and all(torch.isfinite(g).all() for g in grads)


def test_angle_dataset():
    X = np.random.default_rng(1).standard_normal((4, 12, 50, 128)).astype(np.float32)
    Y = np.array([0.0, 90.0, 180.0, 270.0], dtype=np.float32)
    ds = AngleDataset(X, Y)
    xf, yf = ds[0]
    assert xf.shape == (12, 50, 128)
    assert 0.0 <= yf < 2 * np.pi


def test_overfit_tiny_smoke():
    """5 个样本 60 步过拟合冒烟：损失显著下降（管线可训练性）。"""
    torch.manual_seed(3)
    m = ShoNet(n_mics=6)
    opt = torch.optim.Adam(m.parameters(), lr=4e-4)
    X = torch.randn(5, 12, 60, 128)
    th = torch.rand(5) * 2 * np.pi
    tgt = torch.stack([torch.cos(th), torch.sin(th)], -1)
    losses = []
    for _ in range(60):
        loss = torch.mean((m(X) - tgt) ** 2)
        opt.zero_grad(); loss.backward(); opt.step()
        losses.append(float(loss))
    assert losses[-1] < 0.5 * losses[0]


@pytest.mark.slow
def test_quick_train_beats_random():
    """80 语句模拟集（order 4）/ 300 步 / CPU：held-out MAE 显著优于随机 90°。

    论文 clean 19.9° 需 40,295 语句 × 200k 步（≈0.02% 计算量的冒烟口径）。
    """
    from repro.sho.speech import synth_speech, oriented_room_dict
    from repro.sho.ism import simulate_multichannel
    from repro.sho.features import stft_phase_features, angular_mae
    rng = np.random.default_rng(2026)
    feats, angs = [], []
    for i in range(80):
        s = synth_speech(1.0, 16000, rng)
        rd = oriented_room_dict(rng)
        y = simulate_multichannel(s, rd, 16000, max_order=4)
        feats.append(stft_phase_features(y[:, :16000], 16000))
        angs.append(rd["orientation_deg"])
    T = min(f.shape[1] for f in feats)
    X = np.stack([f[:, :T] for f in feats]).astype(np.float32)
    Y = np.array(angs, dtype=np.float32)
    model = ShoNet(6)
    opt = torch.optim.Adam(model.parameters(), lr=4e-4)
    sched = torch.optim.lr_scheduler.LinearLR(opt, 1.0, 0.1, total_iters=300)
    for step in range(300):
        idx = rng.integers(0, 64, 16)                 # 前 64 训练
        xt = torch.from_numpy(X[idx])
        th = torch.from_numpy(np.deg2rad(Y[idx]))
        yt = torch.stack([torch.cos(th), torch.sin(th)], -1)
        loss = torch.mean((model(xt) - yt) ** 2)
        opt.zero_grad(); loss.backward(); opt.step(); sched.step()
    pred = predict_degrees(model, X[64:])
    mae = angular_mae(Y[64:], pred)
    assert mae < 70.0, f"held-out MAE {mae:.1f}° 未显著优于随机 90°"
