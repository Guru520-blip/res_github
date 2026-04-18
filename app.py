"""
Executive Job Search Intelligence — Streamlit Web App
Deploy to Streamlit Cloud: https://streamlit.io/cloud
"""

import streamlit as st
import os
import json
import asyncio
from datetime import datetime, date, timedelta

st.set_page_config(
    page_title="Executive Job Search Intelligence",
    page_icon="🎯",
    layout="wide"
)

# ── API key setup ─────────────────────────────────────────────────────────────

def get_settings():
    """Load settings — from st.secrets (deployed) or .env (local)."""
    key = st.secrets.get("ANTHROPIC_API_KEY", "") if hasattr(st, "secrets") else ""
    if not key:
        key = os.environ.get("ANTHROPIC_API_KEY", "")
    return key


def require_api_key():
    """Show API key input if not configured. Returns key or None."""
    key = get_settings()
    if key:
        os.environ["ANTHROPIC_API_KEY"] = key
        return key

    st.warning("Enter your Anthropic API key to get started.")
    entered = st.text_input(
        "Anthropic API Key",
        type="password",
        placeholder="sk-ant-...",
        help="Get your key at console.anthropic.com"
    )
    if entered:
        os.environ["ANTHROPIC_API_KEY"] = entered
        st.rerun()
    return None


# ── Sidebar navigation ────────────────────────────────────────────────────────

def sidebar():
    st.sidebar.title("🎯 Job Search Intel")
    st.sidebar.markdown("---")

    pages = {
        "🏠 Home": "home",
        "📄 Tailor Resume": "resume",
        "✉️ Generate Emails": "emails",
        "🔍 Find Contact": "contact",
        "📊 View Pipeline": "pipeline",
        "🌐 Discover Companies": "discover",
    }

    choice = st.sidebar.radio("Navigate", list(pages.keys()), label_visibility="collapsed")

    st.sidebar.markdown("---")
    st.sidebar.caption("Optional API keys for email finding:")
    hunter = st.sidebar.text_input("Hunter.io API Key", type="password", key="hunter")
    apollo = st.sidebar.text_input("Apollo.io API Key", type="password", key="apollo")
    if hunter:
        os.environ["HUNTER_API_KEY"] = hunter
    if apollo:
        os.environ["APOLLO_API_KEY"] = apollo

    return pages[choice]


# ── Home ──────────────────────────────────────────────────────────────────────

def page_home():
    from candidate_profile import CANDIDATE

    st.title("Executive Job Search Intelligence")
    st.markdown(f"**Candidate:** {CANDIDATE['name']} &nbsp;|&nbsp; {CANDIDATE['location']}")
    st.markdown("---")

    col1, col2, col3 = st.columns(3)
    col1.metric("Years Experience", CANDIDATE['metrics']['years_experience'])
    col2.metric("Assets Managed", CANDIDATE['metrics']['assets_managed'])
    col3.metric("Revenue Growth", CANDIDATE['metrics']['revenue_growth'])

    col4, col5, col6 = st.columns(3)
    col4.metric("Countries", CANDIDATE['metrics']['countries'])
    col5.metric("Customer Retention", CANDIDATE['metrics']['retention'])
    col6.metric("Current Portfolio", CANDIDATE['metrics']['current_portfolio'])

    st.markdown("---")
    st.subheader("What this tool does")
    st.markdown("""
    | Feature | Description |
    |---------|-------------|
    | **📄 Tailor Resume** | Claude rewrites your resume for one specific company — DOCX + PDF |
    | **✉️ Generate Emails** | Personalized cold email, LinkedIn note, follow-up, cover letter |
    | **🔍 Find Contact** | Multi-layer email finder: Hunter → Apollo → pattern detection |
    | **📊 View Pipeline** | Track all target companies and their status |
    | **🌐 Discover** | Auto-find target companies matching your profile via web search |
    """)

    st.markdown("---")
    st.info("👈 Start with **Tailor Resume** in the sidebar to test the core feature.")


# ── Resume tailoring ──────────────────────────────────────────────────────────

def page_resume():
    st.title("📄 Tailor Resume")
    st.markdown("Claude rewrites your resume specifically for one company and role.")
    st.markdown("---")

    with st.form("resume_form"):
        col1, col2 = st.columns(2)
        company_name = col1.text_input("Company Name *", placeholder="e.g. Eskom")
        sector = col2.text_input("Sector *", placeholder="e.g. Power Generation")

        col3, col4 = st.columns(2)
        country = col3.text_input("Country *", placeholder="e.g. South Africa")
        open_role = col4.text_input("Target Role", placeholder="e.g. COO")

        trigger = st.text_area(
            "Why this company NOW? *",
            placeholder="e.g. Turnaround needed — new PE ownership, expanding into 3 African markets",
            height=80
        )
        jd = st.text_area(
            "Job Description (optional — paste for better ATS score)",
            height=150,
            placeholder="Paste the full job description here for best results..."
        )

        submitted = st.form_submit_button("🚀 Generate Tailored Resume", type="primary")

    if submitted:
        if not company_name or not sector or not country or not trigger:
            st.error("Please fill in Company, Sector, Country, and Trigger fields.")
            return

        from services.resume_builder import ResumeBuilder

        with st.spinner(f"Tailoring resume for {company_name}... (30-60 seconds)"):
            try:
                builder = ResumeBuilder()
                result = builder.tailor_resume(
                    company_name=company_name,
                    sector=sector,
                    country=country,
                    trigger_signal=trigger,
                    open_role=open_role,
                    job_description=jd or None
                )

                st.success("✅ Resume generated successfully!")

                # ATS score
                ats = result.get("ats_report", {})
                score = result.get("ats_score", 0)
                verdict = ats.get("verdict", "")
                col_a, col_b, col_c = st.columns(3)
                col_a.metric("ATS Score", f"{score}/10")
                col_b.metric("Keyword Match", ats.get("keyword_match_rate", "—"))
                col_c.metric("Verdict", verdict)

                tc = result["tailored_content"]

                # Headline + Summary
                st.subheader("Tailored Headline")
                st.info(tc["tailored_headline"])

                st.subheader("Tailored Summary")
                st.write(tc["tailored_summary"])

                # Highlights
                st.subheader("Executive Highlights")
                for h in tc.get("executive_highlights", []):
                    st.markdown(f"- {h}")

                # ATS details
                if ats:
                    with st.expander("🔍 ATS Analysis Detail"):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.markdown("**✅ Matched Keywords**")
                            st.write(", ".join(ats.get("matched_keywords", [])[:10]))
                        with col2:
                            st.markdown("**⚠️ Missing Critical Keywords**")
                            st.write(", ".join(ats.get("missing_critical", [])))
                        st.markdown("**💡 Recommendations**")
                        for r in ats.get("recommendations", []):
                            st.markdown(f"- {r}")

                # Changes made
                with st.expander("📝 Changes Made by Claude"):
                    for c in tc.get("changes_made", []):
                        st.markdown(f"- {c}")
                    st.markdown("**Rationale:**")
                    st.write(tc.get("tailoring_rationale", ""))

                # Download buttons
                st.markdown("---")
                st.subheader("Download Files")
                col_d, col_e = st.columns(2)

                docx_path = result.get("docx_path")
                if docx_path and os.path.exists(docx_path):
                    with open(docx_path, "rb") as f:
                        col_d.download_button(
                            "📥 Download DOCX",
                            data=f.read(),
                            file_name=os.path.basename(docx_path),
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                        )

                pdf_path = result.get("pdf_path")
                if pdf_path and os.path.exists(pdf_path):
                    with open(pdf_path, "rb") as f:
                        col_e.download_button(
                            "📥 Download PDF",
                            data=f.read(),
                            file_name=os.path.basename(pdf_path),
                            mime="application/pdf"
                        )

                # Save to DB
                from database import init_db, get_db, CompanyDB, ResumeDB
                init_db()
                with get_db() as db:
                    cid = CompanyDB.create(db, {
                        "company_name": company_name,
                        "sector": sector,
                        "country": country,
                        "trigger_signal": trigger,
                        "open_role_title": open_role,
                        "job_description": jd or None,
                        "status": "researching",
                        "created_at": datetime.now().isoformat(),
                        "updated_at": datetime.now().isoformat()
                    })
                    ResumeDB.create(db, {
                        "company_id": cid,
                        "target_role": open_role,
                        "tailored_headline": tc["tailored_headline"],
                        "tailored_summary": tc["tailored_summary"],
                        "tailored_experience_json": json.dumps(tc.get("tailored_experience", [])),
                        "achievements_json": json.dumps(tc.get("executive_highlights", [])),
                        "skills_json": json.dumps(tc.get("core_competencies", {})),
                        "changes_made": "\n".join(tc.get("changes_made", [])),
                        "ats_keywords": json.dumps(tc.get("ats_keywords", [])),
                        "ats_score": score,
                        "tailoring_rationale": tc.get("tailoring_rationale", ""),
                        "docx_path": docx_path,
                        "created_at": datetime.now().isoformat()
                    })
                st.caption(f"Saved to pipeline as Company ID {cid}")

            except Exception as e:
                st.error(f"Error: {e}")
                st.exception(e)


# ── Email generation ──────────────────────────────────────────────────────────

def page_emails():
    st.title("✉️ Generate Outreach Emails")
    st.markdown("Generates cold email, LinkedIn note, follow-up, and cover letter.")
    st.markdown("---")

    with st.form("email_form"):
        col1, col2 = st.columns(2)
        company_name = col1.text_input("Company Name *", placeholder="e.g. Acwa Power")
        sector = col2.text_input("Sector *", placeholder="e.g. Renewable Energy")

        col3, col4 = st.columns(2)
        country = col3.text_input("Country *", placeholder="e.g. Saudi Arabia")
        open_role = col4.text_input("Open Role", placeholder="e.g. VP Operations")

        trigger = st.text_area(
            "Company Trigger *",
            placeholder="Why this company now? e.g. Raised $500M for African expansion",
            height=70
        )

        st.markdown("**Decision Maker**")
        col5, col6 = st.columns(2)
        contact_name = col5.text_input("Contact Name *", placeholder="e.g. Ahmed Al-Rashid")
        contact_title = col6.text_input("Contact Title *", placeholder="e.g. Chief Operating Officer")

        col7, col8 = st.columns(2)
        contact_email = col7.text_input("Contact Email", placeholder="e.g. ahmed@company.com")
        recent_activity = col8.text_input(
            "Recent activity (for personalization)",
            placeholder="e.g. Spoke at Africa Energy Forum last week"
        )

        submitted = st.form_submit_button("🚀 Generate All Outreach", type="primary")

    if submitted:
        if not company_name or not sector or not country or not trigger or not contact_name or not contact_title:
            st.error("Please fill in all required (*) fields.")
            return

        from services.email_generator import EmailGenerator

        with st.spinner("Generating personalized outreach... (30-60 seconds)"):
            try:
                gen = EmailGenerator()
                result = gen.generate_all(
                    company_name=company_name,
                    sector=sector,
                    country=country,
                    trigger_signal=trigger,
                    trigger_source="",
                    contact_name=contact_name,
                    contact_title=contact_title,
                    contact_email=contact_email or "",
                    open_role=open_role or None,
                    recent_activity=recent_activity or None,
                )

                st.success("✅ All outreach content generated!")

                cold = result["cold_email"]
                tab1, tab2, tab3, tab4 = st.tabs([
                    "📧 Cold Email", "💼 LinkedIn Note",
                    "🔄 Follow-Up", "📋 Cover Letter"
                ])

                with tab1:
                    st.markdown(f"**Subject:** {cold['subject']}")
                    st.markdown(f"*Word count: {cold.get('word_count', 0)} words*")
                    st.text_area("Email Body", cold["body"], height=350, key="cold_body")
                    col_a, col_b = st.columns(2)
                    col_a.info(f"**Achievement used:** {cold.get('achievement_used', '')}")
                    col_b.info(f"**Personalization:** {cold.get('personalization_element', '')}")

                with tab2:
                    li = result["linkedin_note"]
                    st.text_area("LinkedIn Note", li["note"], height=120, key="li_note")
                    char_count = li.get("character_count", len(li["note"]))
                    color = "🟢" if char_count <= 300 else "🔴"
                    st.caption(f"{color} {char_count}/300 characters")
                    st.info(f"**Hook used:** {li.get('hook', '')}")

                with tab3:
                    fu = result["followup_email"]
                    st.markdown(f"**Subject:** {fu['subject']}")
                    st.markdown("*Send this if no reply after 5 business days*")
                    st.text_area("Follow-up Body", fu["body"], height=250, key="fu_body")
                    st.caption(f"Word count: {fu.get('word_count', 0)} words")

                with tab4:
                    cl = result["cover_letter"]
                    st.text_area(
                        "Cover Letter",
                        cl.get("full_text", cl.get("body", "")),
                        height=500, key="cl_body"
                    )
                    st.caption(f"Word count: {cl.get('word_count', 0)} words")

            except Exception as e:
                st.error(f"Error: {e}")
                st.exception(e)


# ── Contact finder ────────────────────────────────────────────────────────────

def page_contact():
    st.title("🔍 Find Decision Maker Contact")
    st.markdown("Multi-layer email finder: Hunter → Apollo → domain scrape → pattern guess")
    st.markdown("---")

    with st.form("contact_form"):
        col1, col2 = st.columns(2)
        company_name = col1.text_input("Company Name", placeholder="e.g. Eskom")
        domain = col2.text_input("Domain *", placeholder="e.g. eskom.co.za")

        col3, col4 = st.columns(2)
        first_name = col3.text_input("First Name (if known)", placeholder="e.g. André")
        last_name = col4.text_input("Last Name (if known)", placeholder="e.g. de Ruyter")

        submitted = st.form_submit_button("🔍 Find Email", type="primary")

    if submitted:
        if not domain:
            st.error("Domain is required.")
            return

        from services.contact_finder import ContactFinder

        with st.spinner("Searching for contact... (15-30 seconds)"):
            try:
                finder = ContactFinder()

                if first_name and last_name:
                    result = asyncio.run(finder.find_email(
                        first_name=first_name,
                        last_name=last_name,
                        domain=domain,
                        company_name=company_name or "",
                        hunter_key=os.environ.get("HUNTER_API_KEY"),
                        apollo_key=os.environ.get("APOLLO_API_KEY")
                    ))

                    confidence = result.get("confidence", "NONE")
                    color = {"VERIFIED": "🟢", "HIGH": "🔵", "MEDIUM": "🟡", "LOW": "🟠", "NONE": "🔴"}.get(confidence, "⚪")

                    col_a, col_b, col_c = st.columns(3)
                    col_a.metric("Email Found", result.get("recommended_email") or "Not found")
                    col_b.metric("Confidence", f"{color} {confidence}")
                    col_c.metric("Score", f"{result.get('confidence_score', 0)}/100")

                    col_d, col_e = st.columns(2)
                    col_d.metric("Source", result.get("source", "—"))
                    col_e.metric("MX Valid", "✅ Yes" if result.get("mx_valid") else "❌ No")

                    if result.get("all_pattern_guesses"):
                        with st.expander("All pattern guesses"):
                            for g in result["all_pattern_guesses"]:
                                st.code(g)

                else:
                    people = asyncio.run(
                        finder.find_decision_makers_web(company_name or domain, domain)
                    )

                    if people:
                        st.success(f"Found {len(people)} decision makers")
                        for p in people:
                            with st.expander(f"**{p['full_name']}** — {p.get('title', '')}"):
                                em = asyncio.run(finder.find_email(
                                    first_name=p["first_name"],
                                    last_name=p["last_name"],
                                    domain=domain,
                                    company_name=company_name or "",
                                    hunter_key=os.environ.get("HUNTER_API_KEY"),
                                    apollo_key=os.environ.get("APOLLO_API_KEY")
                                ))
                                st.write(f"**Email:** {em.get('recommended_email') or 'Not found'}")
                                st.write(f"**Confidence:** {em.get('confidence', 'NONE')} ({em.get('confidence_score', 0)}/100)")
                                st.write(f"**Source:** {em.get('source', '—')}")
                    else:
                        st.warning("No decision makers found on the company website.")
                        st.info("Try entering First Name and Last Name manually.")

            except Exception as e:
                st.error(f"Error: {e}")
                st.exception(e)


# ── Pipeline ──────────────────────────────────────────────────────────────────

def page_pipeline():
    st.title("📊 Pipeline")
    st.markdown("All target companies tracked in the database.")
    st.markdown("---")

    from database import init_db, get_db, CompanyDB, ContactDB, OutreachDB, ResumeDB
    init_db()

    with get_db() as db:
        companies = CompanyDB.get_all(db)

    if not companies:
        st.info("No companies in pipeline yet. Use **Tailor Resume** or **Generate Emails** to add your first target.")
        return

    import pandas as pd
    rows = []
    for c in companies:
        rows.append({
            "ID": c["id"],
            "Company": c["company_name"],
            "Country": c.get("country", ""),
            "Sector": c.get("sector", ""),
            "Status": c.get("status", ""),
            "Trigger": (c.get("trigger_signal") or "")[:60],
            "Contact": c.get("contact_name") or "—",
            "Added": (c.get("created_at") or "")[:10]
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("View company detail")
    company_id = st.selectbox(
        "Select company",
        options=[c["id"] for c in companies],
        format_func=lambda x: next(
            c["company_name"] for c in companies if c["id"] == x
        )
    )

    if company_id:
        with get_db() as db:
            company = CompanyDB.get_by_id(db, company_id)
            contacts = ContactDB.get_by_company(db, company_id)
            resumes = ResumeDB.get_by_company(db, company_id)
            outreach = OutreachDB.get_by_company(db, company_id)

        st.markdown(f"### {company['company_name']}")
        st.write(f"**Trigger:** {company.get('trigger_signal', '')}")

        if contacts:
            st.markdown("**Contacts:**")
            for c in contacts:
                st.write(f"- {c['full_name']} | {c.get('title','')} | {c.get('email','')} ({c.get('email_status','')})")

        if resumes:
            st.markdown("**Resumes:**")
            for r in resumes:
                st.write(f"- {r.get('docx_path','N/A')} | ATS: {r.get('ats_score',0)}/10")
                st.write(f"  *{r.get('tailored_headline','')}*")

        if outreach:
            out = outreach[0]
            with st.expander("Cold Email"):
                st.write(f"**Subject:** {out.get('email_subject','')}")
                st.text_area("Body", out.get("email_body",""), height=300, key=f"out_{company_id}")
            with st.expander("LinkedIn Note"):
                st.write(out.get("linkedin_note",""))

    # Excel export
    st.markdown("---")
    if st.button("📥 Export Pipeline to Excel"):
        import io
        with get_db() as db:
            all_companies = CompanyDB.get_all(db)
            all_contacts = ContactDB.get_all(db)
            all_outreach = OutreachDB.get_all(db)

        export_rows = []
        for c in all_companies:
            contact = next((ct for ct in all_contacts if ct["company_id"] == c["id"]), {})
            out = next((o for o in all_outreach if o["company_id"] == c["id"]), {})
            export_rows.append({
                "Company": c["company_name"],
                "Country": c.get("country",""),
                "Sector": c.get("sector",""),
                "Status": c.get("status",""),
                "Trigger": c.get("trigger_signal",""),
                "Contact": contact.get("full_name",""),
                "Email": contact.get("email",""),
                "Email Confidence": contact.get("email_status",""),
                "Subject": out.get("email_subject",""),
                "Follow-up Due": out.get("followup_due_date",""),
            })

        buffer = io.BytesIO()
        pd.DataFrame(export_rows).to_excel(buffer, index=False, engine="openpyxl")
        st.download_button(
            "📥 Download Excel",
            data=buffer.getvalue(),
            file_name=f"pipeline_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )


# ── Discover ──────────────────────────────────────────────────────────────────

def page_discover():
    st.title("🌐 Auto-Discover Target Companies")
    st.markdown("Searches the web for companies matching your profile using AI signal extraction.")
    st.markdown("---")

    with st.form("discover_form"):
        col1, col2 = st.columns(2)
        sector_filter = col1.text_input(
            "Sector filter (optional)",
            placeholder="e.g. Infrastructure, Power, EPC"
        )
        geo_filter = col2.text_input(
            "Geography filter (optional)",
            placeholder="e.g. UAE, Africa, Singapore"
        )
        max_results = st.slider("Max companies to find", 5, 30, 15)
        submitted = st.form_submit_button("🔍 Start Discovery", type="primary")

    if submitted:
        from services.signal_scraper import SignalScraper

        custom_queries = None
        if sector_filter or geo_filter:
            base = f'"{sector_filter}" ' if sector_filter else ""
            geo = f'"{geo_filter}" ' if geo_filter else ""
            custom_queries = [
                f'{base}{geo}("VP Operations" OR COO OR "Director Operations") 2025',
                f'{base}{geo}expansion "operations" executive hire 2025',
                f'{base}{geo}("PE acquisition" OR funding) operations 2025',
                f'{base}{geo}("new contract" OR turnaround) COO 2025'
            ]

        progress = st.progress(0, text="Starting search...")
        scraper = SignalScraper()

        with st.spinner("Searching web for signals... this takes 1-2 minutes"):
            try:
                signals = asyncio.run(
                    scraper.run_discovery(
                        custom_queries=custom_queries,
                        max_results=max_results
                    )
                )
            except Exception as e:
                st.error(f"Discovery error: {e}")
                return

        progress.progress(100, text="Done!")

        if not signals:
            st.warning("No signals found. Try different filters or check your SERP_API_KEY.")
            return

        st.success(f"Found {len(signals)} opportunities")

        import pandas as pd
        rows = [{
            "Company": s.get("company_name",""),
            "Country": s.get("country",""),
            "Sector": s.get("sector",""),
            "Trigger": (s.get("trigger_signal",""))[:80],
            "Score": s.get("priority_score", 0)
        } for s in signals]

        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        st.markdown("---")
        st.subheader("Add to pipeline")
        selected = st.multiselect(
            "Select companies to add",
            options=range(len(signals)),
            format_func=lambda i: f"{signals[i]['company_name']} ({signals[i].get('country','')})"
        )

        if st.button("➕ Add Selected to Pipeline") and selected:
            from database import init_db, get_db, CompanyDB
            init_db()
            for i in selected:
                sig = signals[i]
                domain = ""
                if sig.get("website_hint"):
                    domain = (sig["website_hint"]
                        .replace("https://","").replace("http://","")
                        .replace("www.","").split("/")[0])
                with get_db() as db:
                    cid = CompanyDB.create(db, {
                        "company_name": sig.get("company_name",""),
                        "domain": domain,
                        "country": sig.get("country",""),
                        "sector": sig.get("sector",""),
                        "trigger_type": sig.get("trigger_type",""),
                        "trigger_signal": sig.get("trigger_signal",""),
                        "trigger_source_url": sig.get("trigger_source_url",""),
                        "open_role_title": sig.get("open_role_title",""),
                        "priority_score": sig.get("priority_score",0),
                        "status": "discovered",
                        "created_at": datetime.now().isoformat(),
                        "updated_at": datetime.now().isoformat()
                    })
                st.write(f"✅ Added: {sig['company_name']} (ID: {cid})")


# ── Router ────────────────────────────────────────────────────────────────────

def main():
    key = require_api_key()
    if not key:
        return

    page = sidebar()

    if page == "home":
        page_home()
    elif page == "resume":
        page_resume()
    elif page == "emails":
        page_emails()
    elif page == "contact":
        page_contact()
    elif page == "pipeline":
        page_pipeline()
    elif page == "discover":
        page_discover()


if __name__ == "__main__":
    main()
