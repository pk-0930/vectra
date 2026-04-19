import cv2
import os


class FrameExtractor:
    def extract_frames(self, video_path: str, output_base_folder: str = "frames"):
        video_name = os.path.splitext(os.path.basename(video_path))[0]
        output_folder = os.path.join(output_base_folder, video_name)

        if not os.path.exists(output_folder):
            os.makedirs(output_folder)

        cap = cv2.VideoCapture(video_path)
        frame_count = 0

        while True:
            success, frame = cap.read()
            if not success:
                break

            frame_path = os.path.join(output_folder, f"frame_{frame_count}.jpg")
            cv2.imwrite(frame_path, frame)
            frame_count += 1

        cap.release()
        return frame_count, output_folder


def save_frame(video_path: str, frame_number: int, output_path: str):
    cap = cv2.VideoCapture(video_path)

    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
    success, frame = cap.read()

    if success:
        cv2.imwrite(output_path, frame)

    cap.release()

    return success


def save_annotated_frame(video_path: str, frame_number: int, output_path: str, annotate_fn):
    cap = cv2.VideoCapture(video_path)

    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
    success, frame = cap.read()

    if success:
        annotated_frame = annotate_fn(frame)
        cv2.imwrite(output_path, annotated_frame)

    cap.release()

    return success
