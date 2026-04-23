import os
import tempfile

from shared.pose_analyzer import PoseAnalyzer
from analyzers.squat_analyzer import SquatAnalyzer
from shared.frame_extractor import FrameExtractor
from services.blob_storage_service import BlobStorageService


class JobRunner:
    def __init__(self):
        self.frame_extractor = FrameExtractor()
        self.pose_analyzer = PoseAnalyzer()
        self.squat_analyzer = SquatAnalyzer()
        self.blob_storage_service = BlobStorageService()

    def upload_video_for_job(
        self,
        *,
        job_id: str,
        stored_filename: str,
        data: bytes,
        content_type: str | None = None,
    ) -> str:
        video_blob_name = f"{job_id}/{stored_filename}"
        self.blob_storage_service.upload_video(
            blob_name=video_blob_name,
            data=data,
            content_type=content_type,
        )
        return video_blob_name

    def run_squat_job(
        self,
        *,
        video_blob_name: str,
        original_filename: str,
        stored_filename: str,
        job_id: str,
    ) -> dict:
        with tempfile.TemporaryDirectory() as temp_dir:
            local_video_path = os.path.join(temp_dir, stored_filename)
            extracted_frames_dir = os.path.join(temp_dir, "frames")
            annotated_frames_dir = os.path.join(temp_dir, "annotated-frames")

            self.blob_storage_service.download_video_to_file(
                blob_name=video_blob_name,
                destination_path=local_video_path,
            )

            frame_count, frame_folder = self.frame_extractor.extract_frames_to_folder(
                local_video_path,
                extracted_frames_dir,
            )

            self.blob_storage_service.upload_extracted_frames(
                source_directory=frame_folder,
                blob_prefix=f"{job_id}/{os.path.splitext(stored_filename)[0]}",
            )

            pose_results = self.pose_analyzer.analyze_frames(frame_folder)
            squat_report = self.squat_analyzer.analyze(
                pose_results=pose_results,
                video_path=local_video_path,
                frames_folder=frame_folder,
                annotated_output_folder=annotated_frames_dir,
            )

            self.blob_storage_service.upload_annotated_frames(
                source_directory=annotated_frames_dir,
                blob_prefix="",
            )

            return {
                "status": "Video processed",
                "analysis_type": "squat",
                "filename": original_filename,
                "frames_extracted": frame_count,
                "pose_frames_detected": len(pose_results),
                "squat_analysis": squat_report,
            }
