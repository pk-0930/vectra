import cv2


class FrameAnnotator:
    SIDE_LINE_COLOR = (52, 211, 153)
    SIDE_KNEE_COLOR = (59, 130, 246)
    TORSO_LINE_COLOR = (248, 113, 113)
    FRONT_KNEE_COLOR = (59, 130, 246)
    FRONT_ANKLE_COLOR = (249, 115, 22)
    FRONT_WIDTH_COLOR = (34, 197, 94)
    LABEL_BG_COLOR = (15, 23, 42)
    LABEL_TEXT_COLOR = (248, 250, 252)

    def _point(self, frame, x_norm, y_norm):
        height, width = frame.shape[:2]
        x = int(max(0, min(width - 1, round(x_norm * width))))
        y = int(max(0, min(height - 1, round(y_norm * height))))
        return x, y

    def _line_thickness(self, frame):
        height, width = frame.shape[:2]
        return max(6, int(round(max(height, width) / 220)))

    def _point_radius(self, frame):
        return max(8, self._line_thickness(frame) + 2)

    def _label_style(self, frame):
        height, width = frame.shape[:2]
        scale = max(0.7, max(height, width) / 1800)
        thickness = max(2, int(round(scale * 2.2)))
        line_height = max(30, int(round(30 * scale)))
        padding = max(12, int(round(14 * scale)))
        return scale, thickness, line_height, padding

    def _draw_point(self, frame, point, color):
        radius = self._point_radius(frame)
        outline = max(2, self._line_thickness(frame) // 2)
        cv2.circle(frame, point, radius, color, -1)
        cv2.circle(frame, point, radius + outline, (255, 255, 255), outline)

    def _draw_label_block(self, frame, lines):
        if not lines:
            return

        x = 20
        y = 20
        font_scale, text_thickness, line_height, padding = self._label_style(frame)

        max_width = 0
        for line in lines:
            text_size, _ = cv2.getTextSize(
                line,
                cv2.FONT_HERSHEY_SIMPLEX,
                font_scale,
                text_thickness
            )
            max_width = max(max_width, text_size[0])

        block_width = max_width + (padding * 2)
        block_height = (line_height * len(lines)) + padding

        cv2.rectangle(
            frame,
            (x, y),
            (x + block_width, y + block_height),
            self.LABEL_BG_COLOR,
            -1
        )

        baseline_y = y + padding + max(12, int(round(12 * font_scale)))
        for line in lines:
            cv2.putText(
                frame,
                line,
                (x + padding, baseline_y),
                cv2.FONT_HERSHEY_SIMPLEX,
                font_scale,
                self.LABEL_TEXT_COLOR,
                text_thickness,
                cv2.LINE_AA
            )
            baseline_y += line_height

    def annotate_side_view_frame(
        self,
        frame,
        pose,
        preferred_side,
        depth_status,
        torso_lean_status,
    ):
        if frame is None or pose is None or preferred_side is None:
            return frame

        hip_point = self._point(
            frame,
            pose[f"{preferred_side}_hip_x"],
            pose[f"{preferred_side}_hip_y"],
        )
        knee_point = self._point(
            frame,
            pose[f"{preferred_side}_knee_x"],
            pose[f"{preferred_side}_knee_y"],
        )
        shoulder_point = self._point(
            frame,
            pose[f"{preferred_side}_shoulder_x"],
            pose[f"{preferred_side}_shoulder_y"],
        )
        line_thickness = self._line_thickness(frame)
        knee_half_width = max(30, line_thickness * 8)

        cv2.line(frame, hip_point, knee_point, self.SIDE_LINE_COLOR, line_thickness, cv2.LINE_AA)
        cv2.line(
            frame,
            (knee_point[0] - knee_half_width, knee_point[1]),
            (knee_point[0] + knee_half_width, knee_point[1]),
            self.SIDE_KNEE_COLOR,
            line_thickness,
            cv2.LINE_AA
        )
        cv2.line(
            frame,
            hip_point,
            shoulder_point,
            self.TORSO_LINE_COLOR,
            line_thickness,
            cv2.LINE_AA
        )

        self._draw_point(frame, hip_point, self.SIDE_LINE_COLOR)
        self._draw_point(frame, knee_point, self.SIDE_KNEE_COLOR)
        self._draw_point(frame, shoulder_point, self.TORSO_LINE_COLOR)

        self._draw_label_block(
            frame,
            [
                f"Depth: {depth_status.replace('_', ' ').title()}",
                f"Torso: {torso_lean_status.replace('_', ' ').title()}",
            ]
        )

        return frame

    def annotate_front_view_frame(self, frame, pose, knee_tracking_status):
        if frame is None or pose is None:
            return frame

        left_knee = self._point(frame, pose["left_knee_x"], pose["left_knee_y"])
        right_knee = self._point(frame, pose["right_knee_x"], pose["right_knee_y"])
        left_ankle = self._point(frame, pose["left_ankle_x"], pose["left_ankle_y"])
        right_ankle = self._point(frame, pose["right_ankle_x"], pose["right_ankle_y"])
        line_thickness = self._line_thickness(frame)

        self._draw_point(frame, left_knee, self.FRONT_KNEE_COLOR)
        self._draw_point(frame, right_knee, self.FRONT_KNEE_COLOR)
        self._draw_point(frame, left_ankle, self.FRONT_ANKLE_COLOR)
        self._draw_point(frame, right_ankle, self.FRONT_ANKLE_COLOR)

        cv2.line(
            frame,
            left_knee,
            right_knee,
            self.FRONT_WIDTH_COLOR,
            line_thickness,
            cv2.LINE_AA
        )
        cv2.line(
            frame,
            left_ankle,
            right_ankle,
            self.FRONT_WIDTH_COLOR,
            line_thickness,
            cv2.LINE_AA
        )

        self._draw_label_block(
            frame,
            [f"Knee tracking: {knee_tracking_status.replace('_', ' ').title()}"]
        )

        return frame
