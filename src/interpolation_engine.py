"""
Cattle Tracklet Interpolation Engine (1Hz -> 30Hz) - Advanced Robust Version
"""

import math
import numpy as np

def corners_to_bbox_params(points):
    pts = np.array(points, dtype=np.float64)
    cx, cy = np.mean(pts, axis=0)
    
    side_01 = np.linalg.norm(pts[1] - pts[0])
    side_12 = np.linalg.norm(pts[2] - pts[1])
    
    if side_01 >= side_12:
        w = side_01
        h = side_12
        v = pts[1] - pts[0]
        theta = math.atan2(v[1], v[0])
    else:
        w = side_12
        h = side_01
        v = pts[2] - pts[1]
        theta = math.atan2(v[1], v[0])
        
    while theta <= -math.pi / 2:
        theta += math.pi
    while theta > math.pi / 2:
        theta -= math.pi
        
    return cx, cy, w, h, theta


def bbox_params_to_corners(cx, cy, w, h, theta):
    cos_t = math.cos(theta)
    sin_t = math.sin(theta)
    
    local_pts = np.array([
        [-w/2, -h/2],
        [ w/2, -h/2],
        [ w/2,  h/2],
        [-w/2,  h/2]
    ])
    
    world_pts = []
    for x, y in local_pts:
        rx = x * cos_t - y * sin_t + cx
        ry = x * sin_t + y * cos_t + cy
        world_pts.append([rx, ry])
        
    return world_pts


def interpolate_angle(theta0, theta1, t):
    delta = math.atan2(math.sin(theta1 - theta0), math.cos(theta1 - theta0))
    return theta0 + t * delta


def smooth_1d_array(arr, window_size=11):
    if len(arr) < window_size:
        return arr
    
    smoothed = np.copy(arr)
    half_w = window_size // 2
    
    for i in range(len(arr)):
        start = max(0, i - half_w)
        end = min(len(arr), i + half_w + 1)
        smoothed[i] = np.mean(arr[start:end])
        
    return smoothed


def smooth_angles(angles, window_size=11):
    if len(angles) < window_size:
        return angles
        
    sin_vals = np.sin(angles)
    cos_vals = np.cos(angles)
    
    smoothed_sin = smooth_1d_array(sin_vals, window_size)
    smoothed_cos = smooth_1d_array(cos_vals, window_size)
    
    smoothed_angles = np.zeros_like(angles)
    for i in range(len(angles)):
        smoothed_angles[i] = math.atan2(smoothed_sin[i], smoothed_cos[i])
        
    return smoothed_angles


def generate_dense_cache(sparse_json_dict, parse_json_func, total_frames, fps=25.0):
    # 1. Group tracklets by cow ID
    cow_tracks = {}
    for f_no, json_path in sorted(sparse_json_dict.items()):
        boxes = parse_json_func(str(json_path))
        for box in boxes:
            cow_id = box["id"]
            pts = box["points"]
            if len(pts) != 4:
                continue
                
            params = corners_to_bbox_params(pts)
            if cow_id not in cow_tracks:
                cow_tracks[cow_id] = {}
            cow_tracks[cow_id][f_no] = params

    dense_cache = {f: [] for f in range(total_frames)}
    max_gap = int(fps * 2.0)
    smoothing_window = 11

    # 2. Interpolate and Smooth
    for cow_id, tracks in cow_tracks.items():
        sorted_anchor_frames = sorted(tracks.keys())
        if not sorted_anchor_frames:
            continue
            
        temp_track = {} # frame_no -> [cx, cy, w, h, theta]
        
        if len(sorted_anchor_frames) == 1:
            only_f = sorted_anchor_frames[0]
            temp_track[only_f] = tracks[only_f]
        else:
            for i in range(len(sorted_anchor_frames) - 1):
                f0 = sorted_anchor_frames[i]
                f1 = sorted_anchor_frames[i + 1]
                p0 = tracks[f0]
                p1 = tracks[f1]
                
                if (f1 - f0) > max_gap:
                    temp_track[f0] = p0
                    temp_track[f1] = p1
                    continue
                
                for f in range(f0, f1 + 1):
                    if f >= total_frames:
                        break
                    t = 0.0 if f0 == f1 else (f - f0) / (f1 - f0)
                    
                    cx = (1 - t) * p0[0] + t * p1[0]
                    cy = (1 - t) * p0[1] + t * p1[1]
                    w  = (1 - t) * p0[2] + t * p1[2]
                    h  = (1 - t) * p0[3] + t * p1[3]
                    theta = interpolate_angle(p0[4], p1[4], t)
                    
                    temp_track[f] = [cx, cy, w, h, theta]

        # Extract segments for smoothing
        frames_in_track = sorted(temp_track.keys())
        if not frames_in_track:
            continue
            
        segments = []
        current_seg = [frames_in_track[0]]
        for f in frames_in_track[1:]:
            if f == current_seg[-1] + 1:
                current_seg.append(f)
            else:
                segments.append(current_seg)
                current_seg = [f]
        segments.append(current_seg)

        for seg in segments:
            if len(seg) == 0:
                continue
            
            # Extract raw arrays
            cx_arr = np.array([temp_track[f][0] for f in seg])
            cy_arr = np.array([temp_track[f][1] for f in seg])
            w_arr  = np.array([temp_track[f][2] for f in seg])
            h_arr  = np.array([temp_track[f][3] for f in seg])
            th_arr = np.array([temp_track[f][4] for f in seg])
            
            # Apply moving average filter
            cx_smoothed = smooth_1d_array(cx_arr, smoothing_window)
            cy_smoothed = smooth_1d_array(cy_arr, smoothing_window)
            w_smoothed  = smooth_1d_array(w_arr, smoothing_window)
            h_smoothed  = smooth_1d_array(h_arr, smoothing_window)
            th_smoothed = smooth_angles(th_arr, smoothing_window)
            
            # Reconstruct corners and put in dense cache
            for idx, f in enumerate(seg):
                corners = bbox_params_to_corners(
                    cx_smoothed[idx],
                    cy_smoothed[idx],
                    w_smoothed[idx],
                    h_smoothed[idx],
                    th_smoothed[idx]
                )
                dense_cache[f].append({
                    "id": cow_id,
                    "points": corners
                })

    return dense_cache
