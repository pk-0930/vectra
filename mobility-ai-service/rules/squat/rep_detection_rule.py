from shared.pose_utils import get_primary_value


class RepDetectionRule:
    def smooth_signal(self, values, window=5):
        smoothed = []

        for i in range(len(values)):
            start = max(0, i - window)
            end = min(len(values), i + window + 1)
            window_values = values[start:end]
            smoothed.append(sum(window_values) / len(window_values))

        return smoothed

    def percentile(self, values, p):
        if not values:
            return 0.0

        sorted_values = sorted(values)
        index = (len(sorted_values) - 1) * p
        lower = int(index)
        upper = min(lower + 1, len(sorted_values) - 1)
        fraction = index - lower

        return (
            sorted_values[lower] * (1 - fraction) +
            sorted_values[upper] * fraction
        )

    def find_candidate_peaks(self, values, peak_threshold, min_peak_distance):
        raw_peaks = []

        for i in range(1, len(values) - 1):
            if values[i] >= values[i - 1] and values[i] >= values[i + 1]:
                if values[i] >= peak_threshold:
                    raw_peaks.append(i)

        if not raw_peaks:
            return []

        filtered_peaks = []

        for peak in raw_peaks:
            if not filtered_peaks:
                filtered_peaks.append(peak)
                continue

            last_peak = filtered_peaks[-1]

            if (peak - last_peak) < min_peak_distance:
                if values[peak] > values[last_peak]:
                    filtered_peaks[-1] = peak
            else:
                filtered_peaks.append(peak)

        return filtered_peaks

    def find_recovery_frame_before(self, values, peak_idx, recovery_threshold, search_limit=100):
        start = max(0, peak_idx - search_limit)

        for i in range(peak_idx - 1, start - 1, -1):
            if values[i] <= recovery_threshold:
                return i

        return None

    def find_recovery_frame_after(self, values, peak_idx, recovery_threshold, search_limit=100):
        end = min(len(values) - 1, peak_idx + search_limit)

        for i in range(peak_idx + 1, end + 1):
            if values[i] <= recovery_threshold:
                return i

        return None

    def evaluate(self, pose_results, preferred_side=None):
        if len(pose_results) < 30:
            return {
                "squat_detected": False,
                "rep_count": 0,
                "movement_range": 0.0,
                "reps": [],
                "message": "Insufficient pose data for squat analysis."
            }

        hip_y_values = [
            get_primary_value(r, "hip", "y", preferred_side=preferred_side)
            for r in pose_results
        ]

        smoothed_hip_y = self.smooth_signal(hip_y_values, window=5)

        top_baseline = self.percentile(smoothed_hip_y, 0.20)
        bottom_baseline = self.percentile(smoothed_hip_y, 0.80)
        movement_range = bottom_baseline - top_baseline

        if movement_range < 0.05:
            return {
                "squat_detected": False,
                "rep_count": 0,
                "movement_range": float(movement_range),
                "reps": [],
                "message": "No clear squat movement detected."
            }

        peak_threshold = top_baseline + (movement_range * 0.25)
        min_peak_distance = 8

        candidate_peaks = self.find_candidate_peaks(
            smoothed_hip_y,
            peak_threshold=peak_threshold,
            min_peak_distance=min_peak_distance
        )

        reps = []
        used_ranges = []

        for peak_idx in candidate_peaks:
            peak_y = smoothed_hip_y[peak_idx]
            recovery_threshold = peak_y - ((peak_y - top_baseline) * 0.60)

            start_idx = self.find_recovery_frame_before(
                smoothed_hip_y,
                peak_idx,
                recovery_threshold,
                search_limit=120
            )

            end_idx = self.find_recovery_frame_after(
                smoothed_hip_y,
                peak_idx,
                recovery_threshold,
                search_limit=120
            )

            if start_idx is None or end_idx is None:
                continue

            if not (start_idx < peak_idx < end_idx):
                continue

            rep_duration = end_idx - start_idx
            descent_duration = peak_idx - start_idx
            ascent_duration = end_idx - peak_idx

            if rep_duration < 8:
                continue

            if descent_duration < 3 or ascent_duration < 3:
                continue

            descent_depth = peak_y - smoothed_hip_y[start_idx]
            ascent_recovery = peak_y - smoothed_hip_y[end_idx]

            if descent_depth < (movement_range * 0.10):
                continue

            if ascent_recovery < (movement_range * 0.10):
                continue

            overlaps_existing = any(
                not (end_idx < existing_start or start_idx > existing_end)
                for existing_start, existing_end in used_ranges
            )

            if overlaps_existing:
                continue

            used_ranges.append((start_idx, end_idx))

            reps.append({
                "rep_number": len(reps) + 1,
                "start_frame": pose_results[start_idx]["frame_index"],
                "bottom_frame": pose_results[peak_idx]["frame_index"],
                "end_frame": pose_results[end_idx]["frame_index"]
            })

        return {
            "squat_detected": len(reps) > 0,
            "rep_count": len(reps),
            "movement_range": float(movement_range),
            "reps": reps
        }
