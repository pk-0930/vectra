import numpy as np

# Legacy prototype: initial gait/mobility analysis experiment
# Not part of current Vectra product pipeline

def smooth_signal(values, window=5):
    smoothed = []
    for i in range(len(values)):
        start = max(0, i - window)
        end = min(len(values), i + window)
        smoothed.append(sum(values[start:end]) / (end - start))
    return smoothed


def count_direction_changes(values):
    changes = 0
    for i in range(1, len(values) - 1):
        if (values[i] > values[i-1] and values[i] > values[i+1]) or \
           (values[i] < values[i-1] and values[i] < values[i+1]):
            changes += 1
    return changes


def analyze_mobility(pose_results):

    if len(pose_results) < 100:
        return {
            "walking_detected": False,
            "message": "Insufficient pose detection",
            "pose_frames_detected": len(pose_results)
        }

    # Relative motion (knee - hip)
    left_knee_x = [r["left_knee_x"] - r["left_hip_x"] for r in pose_results]
    right_knee_x = [r["right_knee_x"] - r["right_hip_x"] for r in pose_results]

    left_knee_y = [r["left_knee_y"] - r["left_hip_y"] for r in pose_results]
    right_knee_y = [r["right_knee_y"] - r["right_hip_y"] for r in pose_results]

    # Movement ranges
    left_range_x = max(left_knee_x) - min(left_knee_x)
    right_range_x = max(right_knee_x) - min(right_knee_x)

    left_range_y = max(left_knee_y) - min(left_knee_y)
    right_range_y = max(right_knee_y) - min(right_knee_y)

    # Dominant axis
    x_movement = max(left_range_x, right_range_x)
    y_movement = max(left_range_y, right_range_y)

    use_axis = "x" if x_movement > y_movement else "y"

    if use_axis == "x":
        left_positions = left_knee_x
        right_positions = right_knee_x
        left_range = left_range_x
        right_range = right_range_x
    else:
        left_positions = left_knee_y
        right_positions = right_knee_y
        left_range = left_range_y
        right_range = right_range_y

    # Smooth signal
    left_positions = smooth_signal(left_positions)
    right_positions = smooth_signal(right_positions)

    # Correlation
    correlation = np.corrcoef(left_positions, right_positions)[0, 1]

    symmetry_diff = abs(left_range - right_range)

    movement_detected = left_range > 0.01 or right_range > 0.01
    alternating_detected = correlation < 0.7

    # Oscillation detection
    left_changes = count_direction_changes(left_positions)
    right_changes = count_direction_changes(right_positions)

    oscillation_detected = left_changes > 4 and right_changes > 4

    walking_detected = movement_detected and (alternating_detected or oscillation_detected)

    return {
        "walking_detected": bool(walking_detected),
        "dominant_axis": use_axis,
        "left_knee_movement": float(left_range),
        "right_knee_movement": float(right_range),
        "symmetry_difference": float(symmetry_diff),
        "movement_correlation": float(correlation),
        "movement_detected": bool(movement_detected),
        "alternating_detected": bool(alternating_detected),
        "left_step_changes": int(left_changes),
        "right_step_changes": int(right_changes),
        "oscillation_detected": bool(oscillation_detected)
    }