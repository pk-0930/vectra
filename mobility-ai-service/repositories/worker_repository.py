"""Organization-bound worker operations; no HTTP role grants are inferred."""
import json

from repositories.organization_repository import OrganizationRepository


class WorkerRepository(OrganizationRepository):
    def fetch_form_analysis(self, analysis_id):
        return self.fetch_record('form_analyses', analysis_id)

    def mark_form_analysis_running(self, analysis_id, started_at):
        return self.claim_analysis(analysis_id, started_at)

    def update_form_analysis_completion(self, analysis_id, **payload):
        # Only a running claim may complete/fail; forged or duplicate messages
        # cannot overwrite completed results or an analysis in another business.
        with self._connect() as connection:
            row = connection.execute(
                'UPDATE form_analyses SET status=%s, result_json=%s::jsonb, error_message=%s, '
                'updated_at=%s, completed_at=%s WHERE organization_id=%s AND id=%s '
                "AND status='running' RETURNING *",
                (payload['status'], payload['result_json'], payload['error_message'],
                 payload['updated_at'], payload['completed_at'], self.organization_id, analysis_id),
            ).fetchone()
            if row and payload['status'] == 'completed':
                def frames(value):
                    if isinstance(value, dict):
                        for key, item in value.items():
                            if key == 'image_path' and isinstance(item, str):
                                yield item
                            else:
                                yield from frames(item)
                    elif isinstance(value, list):
                        for item in value:
                            yield from frames(item)
                for path in set(frames(json.loads(payload['result_json']))):
                    if not path.startswith(f'/frames/{analysis_id}/'):
                        raise ValueError('Worker produced an unscoped media reference.')
                    connection.execute(
                        'INSERT INTO form_analysis_assets(blob_name,organization_id,analysis_id) VALUES(%s,%s,%s)',
                        (path.removeprefix('/frames/'), self.organization_id, analysis_id),
                    )
            return row

    def mark_form_analysis_queued_for_retry(self, analysis_id, **payload):
        with self._connect() as connection:
            return connection.execute(
                "UPDATE form_analyses SET status='queued', started_at=NULL, completed_at=NULL, "
                'error_message=%s, updated_at=%s WHERE organization_id=%s AND id=%s '
                "AND status='running' RETURNING *",
                (payload['error_message'], payload['updated_at'], self.organization_id, analysis_id),
            ).fetchone()
