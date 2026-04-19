import math


def _get_visibility(pose, visibility_key):
    return float(pose.get(visibility_key, 0.0))


def get_dominant_side(pose_results):
    left_score = 0.0
    right_score = 0.0

    for pose in pose_results:
        left_score += sum(
            _get_visibility(pose, key)
            for key in [
                "left_shoulder_visibility",
                "left_hip_visibility",
                "left_knee_visibility",
                "left_ankle_visibility",
            ]
        )
        right_score += sum(
            _get_visibility(pose, key)
            for key in [
                "right_shoulder_visibility",
                "right_hip_visibility",
                "right_knee_visibility",
                "right_ankle_visibility",
            ]
        )

    return "left" if left_score >= right_score else "right"


def get_primary_side(pose):
    left_score = sum(
        _get_visibility(pose, key)
        for key in [
            "left_shoulder_visibility",
            "left_hip_visibility",
            "left_knee_visibility",
            "left_ankle_visibility",
        ]
    )
    right_score = sum(
        _get_visibility(pose, key)
        for key in [
            "right_shoulder_visibility",
            "right_hip_visibility",
            "right_knee_visibility",
            "right_ankle_visibility",
        ]
    )

    return "left" if left_score >= right_score else "right"


def get_primary_value(pose, joint_name, axis, min_visibility=0.25, preferred_side=None):
    preferred_side = preferred_side or get_primary_side(pose)
    fallback_side = "right" if preferred_side == "left" else "left"

    preferred_visibility = _get_visibility(pose, f"{preferred_side}_{joint_name}_visibility")
    fallback_visibility = _get_visibility(pose, f"{fallback_side}_{joint_name}_visibility")

    if preferred_visibility >= min_visibility:
        return float(pose[f"{preferred_side}_{joint_name}_{axis}"])

    if fallback_visibility >= min_visibility:
        return float(pose[f"{fallback_side}_{joint_name}_{axis}"])

    if preferred_visibility >= fallback_visibility:
        return float(pose[f"{preferred_side}_{joint_name}_{axis}"])

    return float(pose[f"{fallback_side}_{joint_name}_{axis}"])


def get_side_quality(pose, side):
    return min(
        _get_visibility(pose, f"{side}_hip_visibility"),
        _get_visibility(pose, f"{side}_knee_visibility"),
        _get_visibility(pose, f"{side}_ankle_visibility"),
    )


def get_joint_angle(pose, proximal_joint, vertex_joint, distal_joint, preferred_side=None):
    side = preferred_side or get_primary_side(pose)

    ax = float(pose[f"{side}_{proximal_joint}_x"])
    ay = float(pose[f"{side}_{proximal_joint}_y"])
    bx = float(pose[f"{side}_{vertex_joint}_x"])
    by = float(pose[f"{side}_{vertex_joint}_y"])
    cx = float(pose[f"{side}_{distal_joint}_x"])
    cy = float(pose[f"{side}_{distal_joint}_y"])

    ba_x = ax - bx
    ba_y = ay - by
    bc_x = cx - bx
    bc_y = cy - by

    magnitude_ba = math.hypot(ba_x, ba_y)
    magnitude_bc = math.hypot(bc_x, bc_y)

    if magnitude_ba <= 1e-6 or magnitude_bc <= 1e-6:
        return 180.0

    cosine_value = ((ba_x * bc_x) + (ba_y * bc_y)) / (magnitude_ba * magnitude_bc)
    cosine_value = max(-1.0, min(1.0, cosine_value))

    return math.degrees(math.acos(cosine_value))
