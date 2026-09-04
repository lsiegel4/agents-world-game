"""Statistics for the measurement layer.

Small and explicit rather than pulled from a library, so every number in a
result can be traced to the line that produced it.
"""

import math


def gini(values: list) -> float:
    """Inequality over holdings. 0 = everyone equal, 1 = one agent holds all."""
    vals = sorted(v for v in values if v >= 0)
    n = len(vals)
    if n == 0:
        return 0.0
    total = sum(vals)
    if total == 0:
        return 0.0
    cum = sum((i + 1) * v for i, v in enumerate(vals))
    return (2.0 * cum) / (n * total) - (n + 1.0) / n


def entropy(values: list) -> float:
    """Shannon entropy in nats over a non-negative vector, normalized to [0,1]."""
    vals = [v for v in values if v > 0]
    if len(vals) < 2:
        return 0.0
    total = sum(vals)
    h = -sum((v / total) * math.log(v / total) for v in vals)
    return h / math.log(len(vals))


def mean(xs: list) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def pstdev(xs: list) -> float:
    if len(xs) < 2:
        return 0.0
    m = mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / len(xs))


def cohens_d(a: list, b: list) -> float:
    """Standardized difference between two conditions. Reported instead of a
    p-value: with seeds as cheap as these, significance is purchasable and
    effect size is the honest statistic."""
    if len(a) < 2 or len(b) < 2:
        return 0.0
    sa, sb = pstdev(a), pstdev(b)
    pooled = math.sqrt((sa ** 2 + sb ** 2) / 2.0)
    return (mean(a) - mean(b)) / pooled if pooled else 0.0


def _solve(matrix: list, rhs: list) -> list:
    """Gaussian elimination with partial pivoting."""
    n = len(matrix)
    m = [row[:] + [rhs[i]] for i, row in enumerate(matrix)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(m[r][col]))
        if abs(m[piv][col]) < 1e-12:
            return [0.0] * n
        m[col], m[piv] = m[piv], m[col]
        for r in range(n):
            if r == col:
                continue
            f = m[r][col] / m[col][col]
            for c in range(col, n + 1):
                m[r][c] -= f * m[col][c]
    return [m[i][n] / m[i][i] for i in range(n)]


def ols(x_rows: list, y: list) -> dict:
    """Ordinary least squares with an intercept.

    Predictors are standardized first, so the coefficients are directly
    comparable to one another — which is the entire point of DESIGN.md §7.2's
    attribution decomposition. Returns standardized betas and R².
    """
    n, k = len(x_rows), len(x_rows[0])
    if n <= k + 1:
        return {"betas": [0.0] * k, "r2": 0.0, "n": n}

    cols = [[row[j] for row in x_rows] for j in range(k)]
    means = [mean(c) for c in cols]
    sds = [pstdev(c) or 1.0 for c in cols]
    z = [[1.0] + [(row[j] - means[j]) / sds[j] for j in range(k)] for row in x_rows]

    ym, ysd = mean(y), pstdev(y) or 1.0
    zy = [(v - ym) / ysd for v in y]

    p = k + 1
    # Tiny ridge on the diagonal. Predictors here can be near-collinear (an agent
    # far from food is often far from wood), and without this the solve returns
    # all-zero betas silently, which would read as "nothing explains the outcome".
    xtx = [[sum(z[i][a] * z[i][b] for i in range(n)) + (1e-8 if a == b else 0.0)
            for b in range(p)] for a in range(p)]
    xty = [sum(z[i][a] * zy[i] for i in range(n)) for a in range(p)]
    coef = _solve(xtx, xty)

    pred = [sum(coef[a] * z[i][a] for a in range(p)) for i in range(n)]
    ss_res = sum((zy[i] - pred[i]) ** 2 for i in range(n))
    ss_tot = sum(v ** 2 for v in zy)
    r2 = 1.0 - ss_res / ss_tot if ss_tot else 0.0
    return {"betas": coef[1:], "r2": r2, "n": n}
