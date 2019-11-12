import math
import numpy as np
from scipy.linalg import block_diag
import matlab.engine

# Given a time T and waypoints w
# Assign a time each waypoint should be met scaled by distance
def arrangeT(w, T):

    # Subtract each waypoint from previous waypoint
    x = w[:, 1:] - w[:, 0:-1]
    # Get the distance between each consecutive waypoint
    dist = np.sqrt(np.sum(np.square(x), axis=0))
    # Calculate time over total distance
    k = T/sum(dist)
    # Starting at time 0 add each of the distance * delta time
    ts = np.hstack((np.array([0]), np.cumsum(dist*k)))
    # Return the time
    return ts

def computeQ(n, r, t1, t2):
    T = np.zeros(((n-r)*2+1, 1))
    for i in range(0, (n-r)*2+1):
        T[i] = t2**(i+1) - t1**(i+1)

    Q = np.zeros((n+1, n+1))
    for i in range(r, n + 1):
        for j in range(i, n + 1):
            k1 = i - r
            k2 = j - r
            k = k1 + k2 + 1
            Q[i,j] = np.prod(np.arange(k1 + 1,k1 + r + 1)) * np.prod(np.arange(k2 + 1, k2 + r + 1))/k * T[k-1]
            Q[j,i] = Q[i,j]
    return Q

def calc_tvec(t, n_order, r):
    tvec = np.zeros((1, n_order+1))
    for ij in range(r+1, n_order+2):
        tvec[0, ij-1] = np.prod(np.arange(ij-r, ij))*t**(ij-r-1)
    return np.array(tvec).reshape(-1)


def minimum_snap_single_axis_corridor(args):
    waypts, ts, n_order, v0, a0, ve, ae, corridor_r, orig_waypt_indx = args

    # Get the original waypoints
    orig_waypt = waypts[orig_waypt_indx.astype(bool)]

    p0 = waypts[0]
    pe = waypts[-1]

    n_coef = n_order+1
    n_poly = len(waypts)-1

    Q_all = np.array([])
    for i in range(0, n_poly):
        Q_all = block_diag(Q_all, computeQ(n_order, 3, ts[i], ts[i+1]))

    b_all = np.zeros((Q_all.shape[0], 1))

    Aeq = np.zeros((3 * n_poly + 3 + len(orig_waypt), n_coef * n_poly))
    beq = np.zeros((3 * n_poly + 3 + len(orig_waypt), 1))

    Aeq[0: 3, 0: n_coef] = np.array([calc_tvec(ts[0], n_order, 0),
                                     calc_tvec(ts[0], n_order, 1),
                                     calc_tvec(ts[0], n_order, 2)])

    Aeq[3: 6, n_coef * (n_poly - 1):n_coef * n_poly] = np.array([calc_tvec(ts[-1], n_order, 0),
                                                                 calc_tvec(ts[-1], n_order, 1),
                                                                 calc_tvec(ts[-1], n_order, 2)])

    beq[0:6, 0] = np.array([p0, v0, a0, pe, ve, ae]).T
    neq = 5

    # continuous constraints((n_poly - 1) * 3 equations)
    for i in range(0, n_poly - 1):
        tvec_p = calc_tvec(ts[i + 1], n_order, 0)
        tvec_v = calc_tvec(ts[i + 1], n_order, 1)
        tvec_a = calc_tvec(ts[i + 1], n_order, 2)
        neq = neq + 1
        Aeq[neq, n_coef * i:n_coef * (i + 2)] = np.concatenate([tvec_p, -tvec_p])
        neq = neq + 1
        Aeq[neq, n_coef * i: n_coef * (i + 2)] = np.concatenate([tvec_v, -tvec_v])
        neq = neq + 1
        Aeq[neq, n_coef * i: n_coef * (i + 2)] = np.concatenate([tvec_a, -tvec_a])

    # Add constraint to go through waypoints
    i = 0
    for ind in orig_waypt_indx:
        if i >= len(orig_waypt_indx) - 1:
            break
        if ind == 1:
            neq = neq + 1
            tvec_p = calc_tvec(ts[i + 1], n_order, 0)
            Aeq[neq, n_coef * i: n_coef * (i + 1)] = np.array(tvec_p)
            beq[neq] = waypts[i]
        i += 1

    # corridor constraints(n_ploy - 1 iequations)
    Aieq = np.zeros((2 * (n_poly - 1), n_coef * n_poly))
    bieq = np.zeros((2 * (n_poly - 1), 1))

    for i in range(0, n_poly-1):
        tvec_p = calc_tvec(ts[i + 1], n_order, 0)
        i1 = 2 * i
        i2 = 2 * (i + 1)
        i3 = n_coef * (i + 1)
        i4 = n_coef * (i + 2)
        Aieq[i1:i2, i3:i4] = np.array([tvec_p, -tvec_p])
        bieq[i1:i2] = np.array([waypts[i] + corridor_r, corridor_r - waypts[i]]).reshape(2, 1)

    # Start the matlab engine
    eng = matlab.engine.start_matlab()
    Q_all_m = matlab.double(list(Q_all.tolist()))
    b_all_m = matlab.double(list(b_all.tolist()))
    Aieq_m = matlab.double(list(Aieq.tolist()))
    bieq_m = matlab.double(list(bieq.tolist()))
    Aeq_m = matlab.double(list(Aeq.tolist()))
    beq_m = matlab.double(list(beq.tolist()))
    blank = matlab.double([])

    # Default was 200, used 25 to speed it up
    options = eng.optimoptions('quadprog', 'MaxIterations', 50)
    p = eng.quadprog(Q_all_m, b_all_m, Aieq_m, bieq_m, Aeq_m, beq_m, blank, blank, blank, options)

    # # p = quadprog(Q_all, b_all, Aieq, bieq, Aeq, beq)
    # sol = cvxopt.solvers.qp(cvxopt.matrix(Q_all), cvxopt.matrix(b_all), cvxopt.matrix(Aieq), cvxopt.matrix(bieq), cvxopt.matrix(Aeq), cvxopt.matrix(beq))
    # p = np.array(cvxopt.matrix(sol['x']))

    np_p = np.array(p._data.tolist())
    np_p = np_p.reshape(p.size).transpose()

    polys = np_p.reshape(n_poly, n_coef).T

    return polys

def minimum_snap_single_axis_close_form(args):

    wayp, ts, n_order, v0, a0, v1, a1,  = args

    n_coef = n_order+1
    n_poly = len(wayp)-1
    polys = 0
    Q_all = np.array([])
    for i in range(0, n_poly):
        Q_all = block_diag(Q_all, computeQ(n_order, 3, ts[i], ts[i+1]))

    # compute Tk
    tk = np.zeros((n_poly + 1, n_coef))
    for i in range(0, n_coef):
        tk[:, i] = ts[:] ** i

    n_continuous = 3
    A = np.zeros((n_continuous * 2 * n_poly, n_coef * n_poly))
    for i in range(0, n_poly):
        for j in range(0, n_continuous):
            for k in range(j, n_coef):
                if k == j:
                    t1 = 1
                    t2 = 1
                else:
                    t1 = tk[i, k - j]
                    t2 = tk[i + 1, k - j]
                a = np.prod(np.arange(k - j + 1, k+1)) * t1
                b = np.prod(np.arange(k - j + 1, k+1)) * t2
                index11 = n_continuous * 2 * (i) + j
                index12 = n_coef * (i) + k
                A[index11, index12] = a
                index21 = n_continuous * 2 * (i) + n_continuous + j
                index22 = n_coef * (i) + k
                A[index21, index22] = b

    # compute M
    M = np.zeros((n_poly * 2 * n_continuous, n_continuous * (n_poly + 1)))
    for i in range(1, n_poly * 2 + 1):
        j = math.floor(i / 2) + 1
        rbeg = int(n_continuous * (i - 1))
        cbeg = int(n_continuous * (j - 1))
        M[rbeg:rbeg + n_continuous, cbeg:cbeg + n_continuous] = np.eye(n_continuous)

    # compute C
    num_d = n_continuous * (n_poly + 1)
    C = np.eye(num_d)
    df = np.concatenate([wayp, np.array([v0, a0, v1, a1])])
    fix_idx = np.concatenate([np.arange(0, num_d, 3), np.array([1, 2, num_d - 2, num_d-1])])
    free_idx = np.setdiff1d(np.arange(0, num_d), fix_idx)
    C = np.hstack([C[:, fix_idx], C[:, free_idx]])

    AiMC = np.dot(np.dot(np.linalg.inv(A), M), C)
    R = np.dot(np.dot(AiMC.T, Q_all), AiMC)

    n_fix = len(fix_idx)
    Rff = R[0:n_fix, 0:n_fix]
    Rpp = R[n_fix:, n_fix:]
    Rfp = R[0:n_fix, n_fix:]
    Rpf = R[n_fix:, 0:n_fix]

    dp = np.dot(np.dot((-1 * np.linalg.inv(Rpp)), Rfp.T), df)

    p = np.dot(AiMC, np.concatenate([df, dp]))

    polys = p.reshape(n_poly, n_coef).T

    return polys

def poly_val(poly, t, r):
    val = 0
    n = len(poly)-1
    if r <= 0:
        for ind in range(0, n + 1):
            val = val + poly[ind] * t**ind
    else:
        for ind in range(r, n):
            a = poly[ind+1] * np.prod(np.arange(ind-r+1, ind)) * t**(ind-r)
            val = val + a
    return val

def polys_vals(polys, ts, tt, r):
    idx = 0
    N = len(tt)
    vals = np.zeros((1, N)).reshape(N)
    for i in range(0, N):
        t = tt[i]
        if t < ts[idx]:
            vals[i] = 0
        else:
            while idx < len(ts) and t > ts[idx+1] + 0.0001:
                idx = idx+1
            vals[i] = poly_val(polys[:, idx], t, r)

    return vals