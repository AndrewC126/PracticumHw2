"""
End-to-end Playwright tests for the Defect Recurrence Analysis dashboard.

These tests exercise the full stack — browser → Streamlit → PostgreSQL test DB.
They are skipped automatically when the test database is not reachable or when
Playwright browsers have not been installed (`playwright install`).

Run in isolation:
    pytest tests/e2e/ -v
"""

from __future__ import annotations

from playwright.sync_api import Page, expect

# ── Page load ─────────────────────────────────────────────────────────────────


class TestPageLoad:
    def test_title_visible(self, app_page: Page):
        expect(app_page.locator("h1")).to_contain_text("Defect Recurrence Analysis")

    def test_browser_tab_title(self, app_page: Page):
        expect(app_page).to_have_title("Defect Recurrence Analysis")

    def test_caption_explains_recurring_rule(self, app_page: Page):
        # Scope to the caption element to avoid matching the sidebar radio label.
        caption = app_page.locator("[data-testid='stCaptionContainer']")
        expect(caption).to_contain_text("Recurring")

    def test_sidebar_is_rendered(self, app_page: Page):
        sidebar = app_page.locator("[data-testid='stSidebar']")
        expect(sidebar).to_be_visible()

    def test_filters_label_present(self, app_page: Page):
        expect(app_page.locator("text=Filters")).to_be_visible()


# ── Summary table (AC5) ───────────────────────────────────────────────────────


class TestSummaryTable:
    def test_defect_summary_heading(self, app_page: Page):
        expect(app_page.locator("text=Defect Summary").first).to_be_visible()

    def test_dataframe_rendered(self, app_page: Page):
        df = app_page.locator("[data-testid='stDataFrame']").first
        expect(df).to_be_visible()

    def test_burr_defect_code_visible(self, app_page: Page):
        # Streamlit's AG-Grid dataframe virtualises rows; check page body text.
        expect(app_page.locator("body")).to_contain_text("BURR")

    def test_coat_defect_code_visible(self, app_page: Page):
        # Streamlit's AG-Grid dataframe virtualises rows; check page body text instead.
        expect(app_page.locator("body")).to_contain_text("COAT")

    def test_recurring_badge_present(self, app_page: Page):
        expect(app_page.locator("text=Recurring").first).to_be_visible()


# ── Date-range filter (AC6) ───────────────────────────────────────────────────


class TestDateRangeFilter:
    def test_date_input_widget_exists(self, app_page: Page):
        date_input = app_page.locator("[data-testid='stDateInput']")
        expect(date_input).to_be_visible()

    def test_date_input_label(self, app_page: Page):
        expect(app_page.locator("text=Production Date Range")).to_be_visible()


# ── Status filter (AC6) ───────────────────────────────────────────────────────


class TestStatusFilter:
    def test_radio_widget_present(self, app_page: Page):
        radio = app_page.locator("[data-testid='stRadio']")
        expect(radio).to_be_visible()

    def test_all_defects_option_visible(self, app_page: Page):
        expect(app_page.locator("label:has-text('All Defects')")).to_be_visible()

    def test_recurring_only_option_visible(self, app_page: Page):
        expect(app_page.locator("label:has-text('Recurring Only')")).to_be_visible()

    def test_recurring_only_filter_keeps_burr(self, app_page: Page):
        """After switching to 'Recurring Only', BURR (which is Recurring) stays visible."""
        app_page.click("label:has-text('Recurring Only')")
        # Wait for Streamlit to finish re-rendering the dataframe.
        app_page.wait_for_selector("[data-testid='stDataFrame']", state="visible", timeout=10_000)
        app_page.wait_for_timeout(1_000)
        expect(app_page.locator("body")).to_contain_text("BURR")

    def test_recurring_only_hides_insufficient_data_rows(self, app_page: Page):
        """After switching to 'Recurring Only', no '⚠️ Insufficient Data' badge should appear
        in the table (the sidebar label 'Recurring Only' is fine to keep)."""
        app_page.click("label:has-text('Recurring Only')")
        app_page.wait_for_selector("[data-testid='stDataFrame']", state="visible", timeout=10_000)
        app_page.wait_for_timeout(1_000)
        # The Insufficient Data badge in the table should be gone
        insufficient = app_page.locator("[data-testid='stDataFrame'] >> text=Insufficient Data")
        expect(insufficient).to_have_count(0)

    def test_switch_back_to_all_defects(self, app_page: Page):
        """Switching back to All Defects restores the full table."""
        app_page.click("label:has-text('Recurring Only')")
        app_page.wait_for_selector("[data-testid='stDataFrame']", state="visible", timeout=10_000)
        app_page.click("label:has-text('All Defects')")
        app_page.wait_for_selector("[data-testid='stDataFrame']", state="visible", timeout=10_000)
        app_page.wait_for_timeout(1_000)
        expect(app_page.locator("body")).to_contain_text("BURR")


# ── Defect Detail drill-down (AC7) ────────────────────────────────────────────


class TestDefectDetail:
    def test_defect_detail_heading(self, app_page: Page):
        expect(app_page.locator("text=Defect Detail").first).to_be_visible()

    def test_selectbox_present(self, app_page: Page):
        selectbox = app_page.locator("[data-testid='stSelectbox']")
        expect(selectbox).to_be_visible()

    def test_select_defect_code_prompt(self, app_page: Page):
        expect(app_page.locator("text=Select a defect code")).to_be_visible()

    def test_weekly_breakdown_table_visible_for_default_selection(self, app_page: Page):
        """The weekly breakdown table should render for whichever code is pre-selected."""
        expect(app_page.locator("text=Weekly Breakdown").first).to_be_visible()

    def test_underlying_records_table_visible(self, app_page: Page):
        expect(app_page.locator("text=Underlying Inspection Records").first).to_be_visible()

    def test_metric_tiles_rendered(self, app_page: Page):
        """Status / Weeks / Lots / Total metric strip must be visible."""
        expect(app_page.locator("[data-testid='stMetric']").first).to_be_visible()

    def test_select_different_defect_updates_detail(self, app_page: Page):
        """Picking a different code from the selectbox re-renders the detail section."""
        selectbox = app_page.locator("[data-testid='stSelectbox']").first
        selectbox.click()
        # Pick 'WELD' from the dropdown options
        app_page.locator("[data-testid='stSelectboxVirtualDropdown'] >> text=WELD").click()
        app_page.wait_for_timeout(2_000)
        # The detail section should still be visible after the selection
        expect(app_page.locator("text=Weekly Breakdown").first).to_be_visible()


# ── Insufficient Data warning (AC8) ───────────────────────────────────────────


class TestInsufficientDataWarning:
    def test_no_warning_shown_for_recurring_defect(self, app_page: Page):
        """BURR is Recurring in the seed data — no warning should appear for it."""
        selectbox = app_page.locator("[data-testid='stSelectbox']").first
        selectbox.click()
        app_page.locator("[data-testid='stSelectboxVirtualDropdown'] >> text=BURR").click()
        app_page.wait_for_timeout(2_000)
        warning = app_page.locator("[data-testid='stAlertContainer'] >> text=Insufficient Data")
        expect(warning).to_have_count(0)

    def test_no_data_message_not_shown_with_seed_data(self, app_page: Page):
        """With the seeded test database covering the full default date range,
        the 'No defect data found' message must NOT appear — the summary table
        should be visible instead.

        Note: Streamlit's date_input bounds start/end to min_value/max_value
        (the seed data date range), so we cannot navigate the UI to a date
        that produces no lots.  The empty-state logic is exercised by the
        integration test TestFetchSummaryIntegration.
        test_date_range_with_no_defects_returns_insufficient_data.
        """
        expect(app_page.locator("[data-testid='stDataFrame']").first).to_be_visible()
        expect(app_page.locator("text=No defect data found")).to_have_count(0)
