-- A client account claim is an invitation, never a staff role or a name match.
ALTER TABLE identity_actions DROP CONSTRAINT identity_actions_role_check;
ALTER TABLE identity_actions ADD CHECK(role IN ('admin','trainer','client'));
ALTER TABLE identity_actions ADD COLUMN client_id BIGINT;
ALTER TABLE identity_actions ADD FOREIGN KEY(organization_id,client_id) REFERENCES clients(organization_id,id);
ALTER TABLE identity_actions ADD CHECK((role='client' AND client_id IS NOT NULL) OR (role IS DISTINCT FROM 'client' AND client_id IS NULL));
