"""
Executive Job Search Intelligence — Main CLI
Run: python main.py
Interactive menu drives everything.
"""

import os
import json
import asyncio
from datetime import datetime, date, timedelta
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import print as rprint

from database import init_db, get_db, CompanyDB, ContactDB, ResumeDB, OutreachDB
from services.contact_finder import ContactFinder
from services.resume_builder import ResumeBuilder
from services.email_generator import EmailGenerator
from candidate_profile import CANDIDATE
from config import settings

console = Console()


def main():
    """Main application entry point."""
    init_db()
    console.clear()

    console.print(Panel.fit(
        "[bold blue]EXECUTIVE JOB SEARCH INTELLIGENCE[/bold blue]\n"
        f"[dim]Candidate: {CANDIDATE['name']} | "
        f"Location: {CANDIDATE['location']}[/dim]",
        border_style="blue"
    ))

    while True:
        console.print("\n[bold]MAIN MENU[/bold]")
        console.print("  [cyan]1[/cyan]  Add target company + generate all outputs")
        console.print("  [cyan]2[/cyan]  Find decision maker contact")
        console.print("  [cyan]3[/cyan]  Generate tailored resume only")
        console.print("  [cyan]4[/cyan]  Generate outreach emails only")
        console.print("  [cyan]5[/cyan]  View pipeline")
        console.print("  [cyan]6[/cyan]  View all outputs for a company")
        console.print("  [cyan]7[/cyan]  Export pipeline to Excel")
        console.print("  [cyan]8[/cyan]  View follow-ups due")
        console.print("  [cyan]Q[/cyan]  Quit")

        choice = Prompt.ask(
            "\n[bold yellow]Choose[/bold yellow]",
            choices=["1","2","3","4","5","6","7","8","Q","q"]
        )

        if choice == "1":
            flow_add_company_complete()
        elif choice == "2":
            flow_find_contact()
        elif choice == "3":
            flow_resume_only()
        elif choice == "4":
            flow_emails_only()
        elif choice == "5":
            view_pipeline()
        elif choice == "6":
            view_company_outputs()
        elif choice == "7":
            export_pipeline()
        elif choice == "8":
            view_followups_due()
        elif choice.upper() == "Q":
            console.print("\n[dim]Goodbye.[/dim]\n")
            break


def flow_add_company_complete():
    """
    Full end-to-end flow:
    Enter company → Find contact → Generate resume + emails
    """
    console.print(
        "\n[bold cyan]ADD COMPANY & GENERATE ALL OUTPUTS[/bold cyan]"
    )
    console.rule()

    console.print("\n[bold]Step 1: Company Information[/bold]")

    company_name = Prompt.ask("Company name")
    website = Prompt.ask("Company website (e.g. company.com)")
    domain = website.replace("https://","").replace("http://","").replace("www.","").split("/")[0]
    country = Prompt.ask("Country/HQ")
    sector = Prompt.ask(
        "Sector",
        default="Infrastructure"
    )
    size = Prompt.ask(
        "Company size estimate",
        default="500-2000"
    )

    console.print("\n[bold]Step 2: What triggered this target?[/bold]")
    console.print("[dim]Examples: 'Raised $200M Series C', "
                  "'Expanding into 3 African markets', "
                  "'Turnaround needed — new PE ownership'[/dim]")
    trigger_signal = Prompt.ask("Trigger / reason this company NOW")
    trigger_source = Prompt.ask(
        "Source URL (press Enter if none)",
        default=""
    )

    open_role = Prompt.ask(
        "Open role title (press Enter if not advertised)",
        default=""
    )
    role_url = Prompt.ask(
        "Job posting URL (press Enter if none)",
        default=""
    )

    console.print("\n[dim]Paste job description below (press Enter twice when done).[/dim]")
    console.print("[dim]Or press Enter immediately to skip.[/dim]")
    jd_lines = []
    while True:
        line = input()
        if line == "" and jd_lines and jd_lines[-1] == "":
            break
        if line == "" and not jd_lines:
            break
        jd_lines.append(line)
    job_description = "\n".join(jd_lines).strip() or None

    with get_db() as db:
        company_id = CompanyDB.create(db, {
            "company_name": company_name,
            "website_url": f"https://{domain}",
            "domain": domain,
            "country": country,
            "sector": sector,
            "size_estimate": size,
            "trigger_type": "manual",
            "trigger_signal": trigger_signal,
            "trigger_source_url": trigger_source,
            "open_role_url": role_url,
            "open_role_title": open_role,
            "job_description": job_description,
            "status": "researching",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        })

    console.print(f"\n[green]✓[/green] Company saved (ID: {company_id})")

    console.print("\n[bold]Step 3: Decision Maker Contact[/bold]")
    console.print("[dim]Options:[/dim]")
    console.print("  [cyan]A[/cyan]  I know the name — enter manually")
    console.print("  [cyan]B[/cyan]  Search company website automatically")
    console.print("  [cyan]S[/cyan]  Skip contact finding for now")

    contact_choice = Prompt.ask(
        "Choice", choices=["A","a","B","b","S","s"]
    )
    contact_id = None
    contact_data = {}

    if contact_choice.upper() == "A":
        contact_data = _gather_contact_manual(company_id, domain)
        if contact_data:
            with get_db() as db:
                contact_id = ContactDB.create(db, contact_data)
            console.print(f"[green]✓[/green] Contact saved (ID: {contact_id})")

    elif contact_choice.upper() == "B":
        contact_data = _find_contact_auto(
            company_id, company_name, domain
        )
        if contact_data:
            with get_db() as db:
                contact_id = ContactDB.create(db, contact_data)
            console.print(f"[green]✓[/green] Contact saved (ID: {contact_id})")

    console.print("\n[bold]Step 4: Generate All Outputs[/bold]")
    console.print("[dim]This will generate:[/dim]")
    console.print("  ✦  Tailored resume (.docx)")
    console.print("  ✦  Personalized cold email")
    console.print("  ✦  LinkedIn connection note")
    console.print("  ✦  Follow-up email")
    console.print("  ✦  Cover letter")

    if not Confirm.ask("\nProceed with generation?", default=True):
        return

    console.print("\n[bold cyan]Generating tailored resume...[/bold cyan]")
    builder = ResumeBuilder()
    resume_result = builder.tailor_resume(
        company_name=company_name,
        sector=sector,
        country=country,
        trigger_signal=trigger_signal,
        open_role=open_role,
        job_description=job_description,
        contact_name=contact_data.get("full_name"),
        contact_title=contact_data.get("title")
    )

    with get_db() as db:
        resume_id = ResumeDB.create(db, {
            "company_id": company_id,
            "contact_id": contact_id,
            "target_role": open_role,
            "tailored_headline": resume_result["tailored_content"]["tailored_headline"],
            "tailored_summary": resume_result["tailored_content"]["tailored_summary"],
            "tailored_experience_json": json.dumps(
                resume_result["tailored_content"]["tailored_experience"]
            ),
            "achievements_json": json.dumps(
                resume_result["tailored_content"].get("executive_highlights",[])
            ),
            "skills_json": json.dumps(
                resume_result["tailored_content"].get("core_competencies",{})
            ),
            "changes_made": "\n".join(
                resume_result["tailored_content"].get("changes_made",[])
            ),
            "ats_keywords": json.dumps(
                resume_result["tailored_content"].get("ats_keywords",[])
            ),
            "ats_score": resume_result.get("ats_score", 0.0),
            "tailoring_rationale": resume_result["tailored_content"].get(
                "tailoring_rationale",""
            ),
            "docx_path": resume_result["docx_path"],
            "created_at": datetime.now().isoformat()
        })

    console.print(
        f"[green]✓[/green] Resume generated: "
        f"[bold]{resume_result['docx_path']}[/bold]"
    )

    console.print("\n[bold cyan]Generating outreach content...[/bold cyan]")
    generator = EmailGenerator()

    outreach_result = generator.generate_all(
        company_name=company_name,
        sector=sector,
        country=country,
        trigger_signal=trigger_signal,
        trigger_source=trigger_source,
        contact_name=contact_data.get("full_name", "Hiring Manager"),
        contact_title=contact_data.get("title", ""),
        contact_email=contact_data.get("email", ""),
        open_role=open_role,
        recent_activity=contact_data.get("recent_activity"),
        recent_activity_url=contact_data.get("recent_activity_url"),
        job_description=job_description
    )

    followup_date = _add_business_days(date.today(), 5)

    with get_db() as db:
        outreach_id = OutreachDB.create(db, {
            "company_id": company_id,
            "contact_id": contact_id,
            "resume_id": resume_id,
            "email_subject": outreach_result["cold_email"]["subject"],
            "email_body": outreach_result["cold_email"]["body"],
            "linkedin_note": outreach_result["linkedin_note"]["note"],
            "followup_subject": outreach_result["followup_email"]["subject"],
            "followup_body": outreach_result["followup_email"]["body"],
            "cover_letter": outreach_result["cover_letter"]["full_text"],
            "personalization_hooks": json.dumps(
                outreach_result["personalization_hooks"]
            ),
            "word_count": outreach_result["cold_email"].get("word_count", 0),
            "followup_due_date": followup_date.isoformat(),
            "status": "draft",
            "created_at": datetime.now().isoformat()
        })

    console.print(f"[green]✓[/green] Outreach content generated")

    _display_complete_output(
        company_name, contact_data, resume_result, outreach_result,
        company_id, contact_id, resume_id, outreach_id
    )


def _gather_contact_manual(company_id: int, domain: str) -> dict:
    """Gather contact info manually + run email finding."""

    console.print("\n[bold]Enter decision maker details:[/bold]")
    full_name = Prompt.ask("Full name")
    title = Prompt.ask("Title")

    name_parts = full_name.strip().split()
    first_name = name_parts[0] if name_parts else ""
    last_name = name_parts[-1] if len(name_parts) > 1 else ""

    console.print(
        f"\n[dim]Searching for {full_name}'s email at {domain}...[/dim]"
    )

    finder = ContactFinder()
    email_result = asyncio.run(finder.find_email(
        first_name=first_name,
        last_name=last_name,
        domain=domain,
        company_name="",
        hunter_key=settings.HUNTER_API_KEY,
        apollo_key=settings.APOLLO_API_KEY
    ))

    _display_email_result(email_result, full_name, domain)

    final_email = Prompt.ask(
        "Use this email? (press Enter to accept, or type different email)",
        default=email_result.get("recommended_email") or ""
    )

    linkedin = Prompt.ask(
        "LinkedIn URL (optional, press Enter to skip)",
        default=""
    )
    recent_activity = Prompt.ask(
        "Recent activity/quote to personalize (optional)",
        default=""
    )
    recent_url = Prompt.ask(
        "Source URL for activity (optional)",
        default=""
    ) if recent_activity else ""

    return {
        "company_id": company_id,
        "full_name": full_name,
        "first_name": first_name,
        "last_name": last_name,
        "title": title,
        "email": final_email,
        "email_status": email_result.get("confidence","unknown"),
        "email_source": email_result.get("source","manual"),
        "email_confidence_score": email_result.get("confidence_score",0),
        "linkedin_url": linkedin,
        "recent_activity": recent_activity,
        "recent_activity_url": recent_url,
        "is_primary": 1,
        "created_at": datetime.now().isoformat()
    }


def _find_contact_auto(
    company_id: int, company_name: str, domain: str
) -> dict:
    """Auto-find decision makers from company website."""

    console.print(
        f"\n[dim]Searching {domain} for decision makers...[/dim]"
    )

    finder = ContactFinder()
    people = asyncio.run(
        finder.find_decision_makers_web(company_name, domain)
    )

    if not people:
        console.print(
            "[yellow]No decision makers found automatically.[/yellow]"
        )
        console.print(
            "[dim]Try option A (manual entry) instead.[/dim]"
        )
        return {}

    table = Table(title="Decision Makers Found", show_header=True)
    table.add_column("#", style="cyan", width=3)
    table.add_column("Name", style="white")
    table.add_column("Title", style="dim")
    table.add_column("Source", style="dim")

    for i, person in enumerate(people, 1):
        table.add_row(
            str(i),
            person["full_name"],
            person.get("title",""),
            person.get("source","")
        )

    console.print(table)

    choice_num = Prompt.ask(
        "Select person number (or 0 to enter manually)",
        choices=[str(i) for i in range(len(people)+1)]
    )

    if choice_num == "0":
        return _gather_contact_manual(company_id, domain)

    selected = people[int(choice_num) - 1]

    console.print(
        f"\n[dim]Finding email for {selected['full_name']}...[/dim]"
    )

    email_result = asyncio.run(finder.find_email(
        first_name=selected["first_name"],
        last_name=selected["last_name"],
        domain=domain,
        company_name=company_name,
        hunter_key=settings.HUNTER_API_KEY,
        apollo_key=settings.APOLLO_API_KEY
    ))

    _display_email_result(email_result, selected["full_name"], domain)

    final_email = Prompt.ask(
        "Use this email? (Enter to accept, or type different)",
        default=email_result.get("recommended_email") or ""
    )

    recent_activity = Prompt.ask(
        "Recent activity for personalization (optional)",
        default=""
    )

    return {
        "company_id": company_id,
        "full_name": selected["full_name"],
        "first_name": selected["first_name"],
        "last_name": selected["last_name"],
        "title": selected.get("title",""),
        "email": final_email,
        "email_status": email_result.get("confidence","unknown"),
        "email_source": email_result.get("source","auto"),
        "email_confidence_score": email_result.get("confidence_score",0),
        "phone": email_result.get("phone"),
        "recent_activity": recent_activity,
        "is_primary": 1,
        "created_at": datetime.now().isoformat()
    }


def _display_email_result(
    result: dict, name: str, domain: str
):
    """Display email finding result with confidence."""

    confidence = result.get("confidence","NONE")
    score = result.get("confidence_score", 0)
    email = result.get("recommended_email") or result.get("email")

    color_map = {
        "VERIFIED": "green",
        "HIGH": "cyan",
        "MEDIUM": "yellow",
        "LOW": "orange3",
        "NONE": "red"
    }
    color = color_map.get(confidence, "dim")

    console.print(f"\n[bold]Email Finding Result for {name}:[/bold]")

    if email:
        console.print(
            f"  Email:       [{color}]{email}[/{color}]"
        )
        console.print(
            f"  Confidence:  [{color}]{confidence}[/{color}] "
            f"({score}/100)"
        )
        console.print(
            f"  Source:      [dim]{result.get('source','unknown')}[/dim]"
        )
        console.print(
            f"  MX Valid:    "
            f"{'[green]Yes[/green]' if result.get('mx_valid') else '[red]No[/red]'}"
        )
        console.print(
            f"  SMTP Check:  [dim]{result.get('smtp_check','unknown')}[/dim]"
        )

        if result.get("all_pattern_guesses"):
            console.print(
                f"\n  [dim]Other pattern guesses:[/dim]"
            )
            for guess in result["all_pattern_guesses"][:4]:
                console.print(f"    [dim]• {guess}[/dim]")
    else:
        console.print(f"  [red]No email found for {domain}[/red]")
        console.print(
            f"  [dim]MX records: "
            f"{'Found' if result.get('mx_valid') else 'Not found'}[/dim]"
        )


def _display_complete_output(
    company_name, contact_data, resume_result, outreach_result,
    company_id, contact_id, resume_id, outreach_id
):
    """Display all generated outputs clearly."""

    console.print("\n")
    console.rule(f"[bold blue]ALL OUTPUTS FOR {company_name.upper()}[/bold blue]")

    # RESUME
    console.print(Panel(
        f"[bold green]✓ TAILORED RESUME[/bold green]\n\n"
        f"File: [bold]{resume_result['docx_path']}[/bold]\n"
        f"ATS Score: [bold]{resume_result.get('ats_score',0)}/10[/bold]\n\n"
        f"[bold]Headline:[/bold]\n"
        f"{resume_result['tailored_content']['tailored_headline']}\n\n"
        f"[bold]Summary:[/bold]\n"
        f"{resume_result['tailored_content']['tailored_summary']}\n\n"
        f"[bold]Changes Made:[/bold]\n" +
        "\n".join([
            f"  • {c}"
            for c in resume_result['tailored_content'].get('changes_made',[])[:5]
        ]),
        title="[bold]RESUME[/bold]",
        border_style="green"
    ))

    # COLD EMAIL
    cold = outreach_result["cold_email"]
    email_display = (
        f"[bold]TO:[/bold] "
        f"{contact_data.get('email','[no email found]')}\n"
        f"[bold]SUBJECT:[/bold] {cold['subject']}\n\n"
        f"{cold['body']}\n\n"
        f"[dim]Word count: {cold.get('word_count',0)} words[/dim]\n"
        f"[dim]Personalization: {cold.get('personalization_element','')}[/dim]"
    )
    console.print(Panel(
        email_display,
        title="[bold]COLD EMAIL[/bold]",
        border_style="cyan"
    ))

    # LINKEDIN NOTE
    li = outreach_result["linkedin_note"]
    console.print(Panel(
        f"{li['note']}\n\n"
        f"[dim]Characters: {li.get('character_count', len(li['note']))}/300[/dim]\n"
        f"[dim]Hook: {li.get('hook','')}[/dim]",
        title="[bold]LINKEDIN NOTE[/bold]",
        border_style="blue"
    ))

    # FOLLOW-UP
    fu = outreach_result["followup_email"]
    console.print(Panel(
        f"[dim](Send this if no reply after 5 business days)[/dim]\n\n"
        f"[bold]SUBJECT:[/bold] {fu['subject']}\n\n"
        f"{fu['body']}\n\n"
        f"[dim]Word count: {fu.get('word_count',0)} words[/dim]",
        title="[bold]FOLLOW-UP EMAIL[/bold]",
        border_style="yellow"
    ))

    # COVER LETTER
    cl = outreach_result["cover_letter"]
    console.print(Panel(
        cl.get("full_text", cl.get("body","")) + "\n\n"
        f"[dim]Word count: {cl.get('word_count',0)} words[/dim]",
        title="[bold]COVER LETTER[/bold]",
        border_style="magenta"
    ))

    # SUMMARY
    console.print(Panel(
        f"[bold]Company ID:[/bold]  {company_id}\n"
        f"[bold]Contact ID:[/bold]  {contact_id or 'None'}\n"
        f"[bold]Resume ID:[/bold]   {resume_id}\n"
        f"[bold]Outreach ID:[/bold] {outreach_id}\n\n"
        f"[bold]Resume file:[/bold] {resume_result['docx_path']}\n\n"
        f"[bold yellow]NEXT STEPS:[/bold yellow]\n"
        f"  1. Open and review resume: {resume_result['docx_path']}\n"
        f"  2. Copy cold email → send to "
        f"{contact_data.get('email','[find email]')}\n"
        f"  3. Send LinkedIn note\n"
        f"  4. Set reminder: follow-up in 5 business days",
        title="[bold]SUMMARY[/bold]",
        border_style="white"
    ))


def flow_find_contact():
    """Find decision maker contact for any company."""
    console.print("\n[bold cyan]CONTACT FINDER[/bold cyan]")

    company_name = Prompt.ask("Company name")
    domain = Prompt.ask("Domain (e.g. company.com)")
    first_name = Prompt.ask("First name (if known, else press Enter)", default="")
    last_name = Prompt.ask("Last name (if known, else press Enter)", default="")

    finder = ContactFinder()

    if first_name and last_name:
        console.print(f"\n[dim]Searching for {first_name} {last_name}...[/dim]")
        result = asyncio.run(finder.find_email(
            first_name=first_name,
            last_name=last_name,
            domain=domain,
            company_name=company_name,
            hunter_key=settings.HUNTER_API_KEY,
            apollo_key=settings.APOLLO_API_KEY
        ))
        _display_email_result(result, f"{first_name} {last_name}", domain)
    else:
        console.print(
            f"\n[dim]Searching {domain} leadership page...[/dim]"
        )
        people = asyncio.run(
            finder.find_decision_makers_web(company_name, domain)
        )
        if people:
            for person in people:
                console.print(
                    f"\n[bold]{person['full_name']}[/bold] — "
                    f"{person.get('title','')}"
                )
                em = asyncio.run(finder.find_email(
                    first_name=person["first_name"],
                    last_name=person["last_name"],
                    domain=domain,
                    company_name=company_name,
                    hunter_key=settings.HUNTER_API_KEY,
                    apollo_key=settings.APOLLO_API_KEY
                ))
                _display_email_result(em, person["full_name"], domain)
        else:
            console.print("[yellow]No decision makers found.[/yellow]")


def flow_resume_only():
    """Generate tailored resume without full company flow."""
    console.print("\n[bold cyan]TAILORED RESUME GENERATOR[/bold cyan]")

    company_name = Prompt.ask("Company name")
    sector = Prompt.ask("Sector")
    country = Prompt.ask("Country")
    trigger = Prompt.ask("Why this company now / what do they need?")
    open_role = Prompt.ask("Target role title", default="")

    console.print("\n[dim]Paste job description (Enter twice when done, or once to skip):[/dim]")
    jd_lines = []
    while True:
        line = input()
        if line == "" and (not jd_lines or jd_lines[-1] == ""):
            break
        jd_lines.append(line)
    jd = "\n".join(jd_lines).strip() or None

    builder = ResumeBuilder()
    result = builder.tailor_resume(
        company_name=company_name,
        sector=sector,
        country=country,
        trigger_signal=trigger,
        open_role=open_role,
        job_description=jd
    )

    console.print(Panel(
        f"[green]✓ Resume generated[/green]\n\n"
        f"File: [bold]{result['docx_path']}[/bold]\n"
        f"ATS Score: {result.get('ats_score',0)}/10\n\n"
        f"Headline: {result['tailored_content']['tailored_headline']}\n\n"
        f"Tailoring rationale:\n"
        f"{result['tailored_content'].get('tailoring_rationale','')}",
        border_style="green"
    ))


def flow_emails_only():
    """Generate outreach emails only."""
    console.print("\n[bold cyan]OUTREACH EMAIL GENERATOR[/bold cyan]")

    company_name = Prompt.ask("Company name")
    sector = Prompt.ask("Sector")
    country = Prompt.ask("Country")
    trigger = Prompt.ask("Company trigger / why now")
    trigger_source = Prompt.ask("Source URL", default="")
    contact_name = Prompt.ask("Contact name")
    contact_title = Prompt.ask("Contact title")
    contact_email = Prompt.ask("Contact email (or best guess)")
    open_role = Prompt.ask("Open role (optional)", default="")
    recent_activity = Prompt.ask(
        "Recent quote/article/activity (optional)", default=""
    )

    generator = EmailGenerator()
    result = generator.generate_all(
        company_name=company_name,
        sector=sector,
        country=country,
        trigger_signal=trigger,
        trigger_source=trigger_source,
        contact_name=contact_name,
        contact_title=contact_title,
        contact_email=contact_email,
        open_role=open_role,
        recent_activity=recent_activity or None
    )

    _display_complete_output(
        company_name,
        {"email": contact_email, "full_name": contact_name},
        {"tailored_content": {"tailored_headline": "", "tailored_summary": "",
         "changes_made": []}, "docx_path": "N/A", "ats_score": 0},
        result, 0, 0, 0, 0
    )


def view_pipeline():
    """Display pipeline as rich table."""
    with get_db() as db:
        companies = CompanyDB.get_all(db)

    if not companies:
        console.print("[yellow]No companies in pipeline yet.[/yellow]")
        return

    table = Table(
        title="PIPELINE", show_header=True,
        header_style="bold blue"
    )
    table.add_column("ID", style="dim", width=4)
    table.add_column("Company", style="bold white")
    table.add_column("Country", style="dim")
    table.add_column("Sector", style="dim")
    table.add_column("Status", style="cyan")
    table.add_column("Contact", style="dim")
    table.add_column("Email Conf.", style="dim")
    table.add_column("Added", style="dim")

    for c in companies:
        status_colors = {
            "discovered": "dim",
            "researching": "yellow",
            "ready": "cyan",
            "contacted": "blue",
            "replied": "green",
            "meeting": "green bold",
            "passed": "red dim"
        }
        color = status_colors.get(c.get("status",""), "white")

        contact_name = c.get("contact_name","—")
        email_conf = c.get("email_status","—")
        conf_colors = {
            "VERIFIED":"green","HIGH":"cyan",
            "MEDIUM":"yellow","LOW":"orange3","NONE":"red"
        }
        ec_color = conf_colors.get(email_conf,"dim")

        added = c.get("created_at","")[:10] if c.get("created_at") else ""

        table.add_row(
            str(c["id"]),
            c["company_name"],
            c.get("country",""),
            c.get("sector",""),
            f"[{color}]{c.get('status','')}[/{color}]",
            contact_name,
            f"[{ec_color}]{email_conf}[/{ec_color}]",
            added
        )

    console.print(table)


def view_company_outputs():
    """View all outputs for a specific company."""
    view_pipeline()
    company_id = Prompt.ask("\nEnter company ID to view outputs")

    with get_db() as db:
        company = CompanyDB.get_by_id(db, int(company_id))
        contacts = ContactDB.get_by_company(db, int(company_id))
        resumes = ResumeDB.get_by_company(db, int(company_id))
        outreach = OutreachDB.get_by_company(db, int(company_id))

    if not company:
        console.print("[red]Company not found.[/red]")
        return

    console.print(f"\n[bold]{company['company_name']}[/bold] — "
                  f"{company.get('country','')} | "
                  f"{company.get('sector','')}")
    console.print(f"Trigger: {company.get('trigger_signal','')}")

    if contacts:
        console.print(f"\n[bold]Contacts ({len(contacts)}):[/bold]")
        for c in contacts:
            conf = c.get("email_status","")
            conf_colors = {
                "VERIFIED":"green","HIGH":"cyan",
                "MEDIUM":"yellow","LOW":"orange3"
            }
            col = conf_colors.get(conf,"dim")
            console.print(
                f"  {c['full_name']} | {c.get('title','')} | "
                f"[{col}]{c.get('email','')}[/{col}] "
                f"({conf})"
            )

    if resumes:
        console.print(f"\n[bold]Resumes ({len(resumes)}):[/bold]")
        for r in resumes:
            console.print(
                f"  [{r['id']}] {r.get('docx_path','N/A')} | "
                f"ATS: {r.get('ats_score',0)}/10"
            )
            console.print(
                f"       Headline: {r.get('tailored_headline','')}"
            )

    if outreach:
        out = outreach[0]
        console.print(f"\n[bold]Outreach:[/bold]")
        console.print(
            f"  Status: {out.get('status','draft')}\n"
            f"  Subject: {out.get('email_subject','')}\n\n"
            f"  [bold]Email body:[/bold]\n{out.get('email_body','')}\n\n"
            f"  [bold]LinkedIn note:[/bold]\n{out.get('linkedin_note','')}"
        )


def export_pipeline():
    """Export full pipeline to Excel."""
    import pandas as pd

    with get_db() as db:
        companies = CompanyDB.get_all(db)
        all_outreach = OutreachDB.get_all(db)
        all_contacts = ContactDB.get_all(db)

    if not companies:
        console.print("[yellow]No data to export.[/yellow]")
        return

    rows = []
    for c in companies:
        contact = next(
            (ct for ct in all_contacts
             if ct["company_id"] == c["id"]), {}
        )
        out = next(
            (o for o in all_outreach
             if o["company_id"] == c["id"]), {}
        )
        rows.append({
            "Company": c["company_name"],
            "Country": c.get("country",""),
            "Sector": c.get("sector",""),
            "Status": c.get("status",""),
            "Trigger": c.get("trigger_signal",""),
            "Open Role": c.get("open_role_title",""),
            "Contact Name": contact.get("full_name",""),
            "Contact Title": contact.get("title",""),
            "Email": contact.get("email",""),
            "Email Confidence": contact.get("email_status",""),
            "Email Score": contact.get("email_confidence_score",""),
            "LinkedIn": contact.get("linkedin_url",""),
            "Email Subject": out.get("email_subject",""),
            "Outreach Status": out.get("status",""),
            "Sent At": out.get("sent_at",""),
            "Follow-up Due": out.get("followup_due_date",""),
            "Reply Received": out.get("reply_received",""),
            "Date Added": c.get("created_at","")[:10] if c.get("created_at") else ""
        })

    df = pd.DataFrame(rows)
    os.makedirs("output", exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    path = f"output/pipeline_{ts}.xlsx"

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Pipeline", index=False)
        ws = writer.sheets["Pipeline"]
        for col in ws.columns:
            max_len = max(
                len(str(cell.value or "")) for cell in col
            )
            ws.column_dimensions[col[0].column_letter].width = min(
                max_len + 2, 50
            )

    console.print(f"[green]✓[/green] Exported to: [bold]{path}[/bold]")


def view_followups_due():
    """Show follow-ups due today or overdue."""
    today = date.today().isoformat()

    with get_db() as db:
        due = OutreachDB.get_followups_due(db, today)

    if not due:
        console.print("[green]No follow-ups due.[/green]")
        return

    console.print(f"\n[bold yellow]FOLLOW-UPS DUE ({len(due)})[/bold yellow]\n")

    for item in due:
        console.print(
            f"[bold]{item['company_name']}[/bold] — "
            f"{item.get('contact_name','Unknown')}\n"
            f"  Due: {item.get('followup_due_date','')}\n"
            f"  Original sent: {item.get('sent_at','not sent yet')}\n"
            f"  Subject: Re: {item.get('email_subject','')}\n"
        )


def _add_business_days(start: date, days: int) -> date:
    """Add N business days to a date."""
    current = start
    added = 0
    while added < days:
        current += timedelta(days=1)
        if current.weekday() < 5:  # Mon-Fri
            added += 1
    return current


if __name__ == "__main__":
    main()
