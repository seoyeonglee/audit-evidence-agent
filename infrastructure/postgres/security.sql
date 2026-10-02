-- Apply as migration owner. Runtime role must not own tables, be superuser, or BYPASSRLS.
CREATE OR REPLACE FUNCTION forbid_audit_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'audit events are append-only'; END; $$;
DROP TRIGGER IF EXISTS immutable_audit ON audit_events;
CREATE TRIGGER immutable_audit BEFORE UPDATE OR DELETE ON audit_events
FOR EACH ROW EXECUTE FUNCTION forbid_audit_mutation();
DO $$ DECLARE t text; BEGIN
  FOREACH t IN ARRAY ARRAY['requests','documents','jobs','audit_events'] LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
    EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
    EXECUTE format('DROP POLICY IF EXISTS tenant_boundary ON %I', t);
    EXECUTE format('CREATE POLICY tenant_boundary ON %I USING (tenant_id = current_setting(''app.tenant_id'', true)) WITH CHECK (tenant_id = current_setting(''app.tenant_id'', true))', t);
  END LOOP;
END $$;
