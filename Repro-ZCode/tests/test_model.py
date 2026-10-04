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
