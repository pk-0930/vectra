import unittest
from unittest.mock import Mock

from services.job_runner import JobRunner


class JobRunnerScopeTests(unittest.TestCase):
    def test_uploaded_frame_names_and_result_references_share_analysis_namespace(self):
        runner = JobRunner.__new__(JobRunner)
        runner.frame_extractor = Mock()
        runner.frame_extractor.extract_frames_to_folder.return_value = (1, '/tmp/unused-test-frames')
        runner.pose_analyzer = Mock()
        runner.pose_analyzer.analyze_frames.return_value = []
        runner.squat_analyzer = Mock()
        runner.squat_analyzer.analyze.return_value = {'frames': {
            'rep_frames': [{'image_path': '/frames/rep.jpg?v=2'}],
            'knee_frame': {'image_path': '/frames/knee.jpg?v=3'},
        }}
        runner.blob_storage_service = Mock()
        result = runner.run_squat_job(video_blob_name='analysis/video.mp4',
            original_filename='video.mp4', stored_filename='video.mp4', job_id='analysis')
        self.assertEqual(runner.blob_storage_service.upload_annotated_frames.call_args.kwargs['blob_prefix'], 'analysis')
        frames = result['squat_analysis']['frames']
        self.assertEqual(frames['rep_frames'][0]['image_path'], '/frames/analysis/rep.jpg')
        self.assertEqual(frames['knee_frame']['image_path'], '/frames/analysis/knee.jpg')
