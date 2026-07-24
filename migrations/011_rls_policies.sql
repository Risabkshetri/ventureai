-- 011_rls_policies.sql
-- Row Level Security policies for all tables.
--
-- Conventions:
--   • auth.uid()  → the UUID of the currently authenticated Supabase user
--   • service_role bypasses RLS entirely (used by the backend for writes)
--   • Helper sub-selects check the users table for role-based access
--
-- Run this AFTER all table-creation migrations (000–010).


-- ═════════════════════════════════════════════════════════════════════════════
-- HELPER: reusable function to get the current user's role
-- ═════════════════════════════════════════════════════════════════════════════
CREATE OR REPLACE FUNCTION public.current_user_role()
RETURNS text
LANGUAGE sql
STABLE
SECURITY DEFINER
AS $$
    SELECT role::text FROM public.users WHERE id = auth.uid();
$$;


-- ═════════════════════════════════════════════════════════════════════════════
-- 1. USERS
-- ═════════════════════════════════════════════════════════════════════════════

-- Users can read their own row.
CREATE POLICY users_select_own
    ON users FOR SELECT
    USING (id = auth.uid());

-- Users can update their own row (name, email, etc. — password changes go
-- through Supabase Auth, not this table directly).
CREATE POLICY users_update_own
    ON users FOR UPDATE
    USING (id = auth.uid())
    WITH CHECK (id = auth.uid());

-- No INSERT policy — user creation is handled by the signup flow using the
-- service_role key, which bypasses RLS.


-- ═════════════════════════════════════════════════════════════════════════════
-- 2. STARTUPS
-- ═════════════════════════════════════════════════════════════════════════════

-- Founders can read their own startups.
CREATE POLICY startups_select_own
    ON startups FOR SELECT
    USING (founder_id = auth.uid());

-- Investors and admins can read ALL startups (read-only).
CREATE POLICY startups_select_investor_admin
    ON startups FOR SELECT
    USING (public.current_user_role() IN ('investor', 'admin'));

-- Founders can create startups (must set themselves as founder).
CREATE POLICY startups_insert_founder
    ON startups FOR INSERT
    WITH CHECK (founder_id = auth.uid());

-- Founders can update their own startups.
CREATE POLICY startups_update_founder
    ON startups FOR UPDATE
    USING (founder_id = auth.uid())
    WITH CHECK (founder_id = auth.uid());

-- Founders can delete their own startups.
CREATE POLICY startups_delete_founder
    ON startups FOR DELETE
    USING (founder_id = auth.uid());


-- ═════════════════════════════════════════════════════════════════════════════
-- 3. EVALUATIONS
--    Readable by owning founder (via startup) and any investor.
--    Writable only via service_role (system-generated).
-- ═════════════════════════════════════════════════════════════════════════════

-- Founders can read evaluations for their own startups.
CREATE POLICY evaluations_select_founder
    ON evaluations FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM startups
            WHERE startups.id = evaluations.startup_id
              AND startups.founder_id = auth.uid()
        )
    );

-- Investors can read all evaluations.
CREATE POLICY evaluations_select_investor
    ON evaluations FOR SELECT
    USING (public.current_user_role() = 'investor');


-- ═════════════════════════════════════════════════════════════════════════════
-- 4. PDF_METADATA
--    Same read pattern as evaluations. Writable only via service_role.
-- ═════════════════════════════════════════════════════════════════════════════

-- Founders can read PDF metadata for their own evaluations.
CREATE POLICY pdf_metadata_select_founder
    ON pdf_metadata FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM evaluations
            JOIN startups ON startups.id = evaluations.startup_id
            WHERE evaluations.id = pdf_metadata.evaluation_id
              AND startups.founder_id = auth.uid()
        )
    );

-- Investors can read all PDF metadata.
CREATE POLICY pdf_metadata_select_investor
    ON pdf_metadata FOR SELECT
    USING (public.current_user_role() = 'investor');


-- ═════════════════════════════════════════════════════════════════════════════
-- 5. EXECUTIVE_SUMMARIES
--    Same read pattern. Writable only via service_role.
-- ═════════════════════════════════════════════════════════════════════════════

-- Founders can read executive summaries for their own evaluations.
CREATE POLICY executive_summaries_select_founder
    ON executive_summaries FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM evaluations
            JOIN startups ON startups.id = evaluations.startup_id
            WHERE evaluations.id = executive_summaries.evaluation_id
              AND startups.founder_id = auth.uid()
        )
    );

-- Investors can read all executive summaries.
CREATE POLICY executive_summaries_select_investor
    ON executive_summaries FOR SELECT
    USING (public.current_user_role() = 'investor');


-- ═════════════════════════════════════════════════════════════════════════════
-- 6. IDENTIFIED_RISKS
--    Same read pattern. Writable only via service_role.
-- ═════════════════════════════════════════════════════════════════════════════

-- Founders can read risks for their own evaluations.
CREATE POLICY identified_risks_select_founder
    ON identified_risks FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM evaluations
            JOIN startups ON startups.id = evaluations.startup_id
            WHERE evaluations.id = identified_risks.evaluation_id
              AND startups.founder_id = auth.uid()
        )
    );

-- Investors can read all risks.
CREATE POLICY identified_risks_select_investor
    ON identified_risks FOR SELECT
    USING (public.current_user_role() = 'investor');


-- ═════════════════════════════════════════════════════════════════════════════
-- 7. INVESTOR_QUESTIONS
--    Same read pattern. Writable only via service_role.
-- ═════════════════════════════════════════════════════════════════════════════

-- Founders can read questions for their own evaluations.
CREATE POLICY investor_questions_select_founder
    ON investor_questions FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM evaluations
            JOIN startups ON startups.id = evaluations.startup_id
            WHERE evaluations.id = investor_questions.evaluation_id
              AND startups.founder_id = auth.uid()
        )
    );

-- Investors can read all questions.
CREATE POLICY investor_questions_select_investor
    ON investor_questions FOR SELECT
    USING (public.current_user_role() = 'investor');


-- ═════════════════════════════════════════════════════════════════════════════
-- 8. SCORES
--    Same read pattern. Writable only via service_role.
-- ═════════════════════════════════════════════════════════════════════════════

-- Founders can read scores for their own evaluations.
CREATE POLICY scores_select_founder
    ON scores FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM evaluations
            JOIN startups ON startups.id = evaluations.startup_id
            WHERE evaluations.id = scores.evaluation_id
              AND startups.founder_id = auth.uid()
        )
    );

-- Investors can read all scores.
CREATE POLICY scores_select_investor
    ON scores FOR SELECT
    USING (public.current_user_role() = 'investor');


-- ═════════════════════════════════════════════════════════════════════════════
-- 9. FINAL_REPORTS
--    Same read pattern. Writable only via service_role.
-- ═════════════════════════════════════════════════════════════════════════════

-- Founders can read reports for their own evaluations.
CREATE POLICY final_reports_select_founder
    ON final_reports FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM evaluations
            JOIN startups ON startups.id = evaluations.startup_id
            WHERE evaluations.id = final_reports.evaluation_id
              AND startups.founder_id = auth.uid()
        )
    );

-- Investors can read all reports.
CREATE POLICY final_reports_select_investor
    ON final_reports FOR SELECT
    USING (public.current_user_role() = 'investor');


-- ═════════════════════════════════════════════════════════════════════════════
-- 10. INVESTOR_ACTIONS
-- ═════════════════════════════════════════════════════════════════════════════

-- Investors can see their own actions.
CREATE POLICY investor_actions_select_own
    ON investor_actions FOR SELECT
    USING (investor_id = auth.uid());

-- Founders can see actions on their own startups
-- (e.g. "who shortlisted my startup").
CREATE POLICY investor_actions_select_founder
    ON investor_actions FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM startups
            WHERE startups.id = investor_actions.startup_id
              AND startups.founder_id = auth.uid()
        )
    );

-- Investors can create their own actions.
CREATE POLICY investor_actions_insert_investor
    ON investor_actions FOR INSERT
    WITH CHECK (investor_id = auth.uid());

-- Investors can remove their own actions (un-shortlist, etc.).
CREATE POLICY investor_actions_delete_investor
    ON investor_actions FOR DELETE
    USING (investor_id = auth.uid());

-- ═════════════════════════════════════════════════════════════════════════════
-- 11. VERIFICATION_REPORTS
--    Same read pattern. Writable only via service_role.
-- ═════════════════════════════════════════════════════════════════════════════

-- Founders can read verification reports for their own evaluations.
CREATE POLICY verification_reports_select_founder
    ON verification_reports FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM evaluations
            JOIN startups ON startups.id = evaluations.startup_id
            WHERE evaluations.id = verification_reports.evaluation_id
              AND startups.founder_id = auth.uid()
        )
    );

-- Investors can read all verification reports.
CREATE POLICY verification_reports_select_investor
    ON verification_reports FOR SELECT
    USING (public.current_user_role() = 'investor');

