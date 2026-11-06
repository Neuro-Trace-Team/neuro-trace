"""PDF report generation for pseudonymized examination documentation."""

from html import escape
from io import BytesIO
from json import dumps
from uuid import UUID

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.medical import (
    Analysis,
    AnalysisResult,
    EEGChannel,
    Examination,
    ExaminationChannel,
    ExaminationEvent,
    PainAssessment,
)


def _text(value: object | None) -> str:
    return "—" if value is None else escape(str(value))


def _latest_doctor_pain(session: Session, examination_id: UUID) -> PainAssessment | None:
    return session.scalar(
        select(PainAssessment)
        .where(PainAssessment.examination_id == examination_id)
        .order_by(PainAssessment.assessed_at.desc(), PainAssessment.created_at.desc())
        .limit(1)
    )


def _latest_completed_analysis(
    session: Session, examination_id: UUID
) -> tuple[Analysis, AnalysisResult] | None:
    return session.execute(
        select(Analysis, AnalysisResult)
        .join(AnalysisResult, AnalysisResult.analysis_id == Analysis.id)
        .where(Analysis.examination_id == examination_id, Analysis.status == "COMPLETED")
        .order_by(Analysis.completed_at.desc(), AnalysisResult.created_at.desc())
        .limit(1)
    ).one_or_none()


def create_bulk_examination_report(session: Session, examinations: list[Examination]) -> bytes:
    """Return an in-memory PDF report without source EEG bytes or storage credentials."""
    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title="NeuroTrace examination report",
    )
    styles = getSampleStyleSheet()
    story = [Paragraph("NeuroTrace — Examination Report", styles["Title"])]
    story.append(Paragraph("Pseudonymized clinical documentation draft", styles["Normal"]))
    story.append(Spacer(1, 7 * mm))

    for index, examination in enumerate(examinations, start=1):
        story.append(Paragraph(f"Examination {index}", styles["Heading2"]))
        details = [
            ["Patient UUID", _text(examination.patient_id)],
            ["Examination UUID", _text(examination.id)],
            ["Examination date", _text(examination.examination_date)],
            ["Uploaded at", _text(examination.created_at)],
            ["Source file", _text(examination.original_filename)],
            ["Format / size", f"{_text(examination.file_format)} / {examination.file_size_bytes} bytes"],
            ["Sampling frequency", f"{examination.sampling_frequency} Hz"],
            ["Duration", f"{_text(examination.duration_seconds)} s"],
            ["Processing status", _text(examination.processing_status)],
        ]
        table = Table(details, colWidths=(48 * mm, 116 * mm), hAlign="LEFT")
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#E8EEF7")),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#B8C2D1")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("PADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        story.extend([table, Spacer(1, 4 * mm)])

        channels = list(
            session.scalars(
                select(EEGChannel.code)
                .join(ExaminationChannel, ExaminationChannel.channel_id == EEGChannel.id)
                .where(ExaminationChannel.examination_id == examination.id)
                .order_by(ExaminationChannel.position)
            )
        )
        story.append(Paragraph(f"EEG channels: {_text(', '.join(channels) if channels else 'not recorded')}", styles["Normal"]))

        doctor_pain = _latest_doctor_pain(session, examination.id)
        if doctor_pain is not None:
            story.append(
                Paragraph(
                    f"Latest clinician pain assessment: {_text(doctor_pain.pain_level)} "
                    f"({_text(doctor_pain.scale)}), assessed {_text(doctor_pain.assessed_at)}",
                    styles["Normal"],
                )
            )
        else:
            story.append(Paragraph("Latest clinician pain assessment: not recorded", styles["Normal"]))

        analysis = _latest_completed_analysis(session, examination.id)
        if analysis is not None:
            analysis_record, result = analysis
            summary = dumps(result.result_json, ensure_ascii=False) if result.result_json is not None else "not recorded"
            story.append(
                Paragraph(
                    f"Latest completed AI analysis: {_text(analysis_record.model_name)} "
                    f"({_text(analysis_record.model_version)}); pain level: {_text(result.pain_level)}; "
                    f"confidence: {_text(result.confidence)}; summary: {_text(summary)}",
                    styles["Normal"],
                )
            )
        else:
            story.append(Paragraph("Latest completed AI analysis: not recorded", styles["Normal"]))

        events = list(
            session.scalars(
                select(ExaminationEvent)
                .where(ExaminationEvent.examination_id == examination.id)
                .order_by(ExaminationEvent.timestamp, ExaminationEvent.created_at)
            )
        )
        story.append(Spacer(1, 3 * mm))
        story.append(Paragraph("Recorded events", styles["Heading3"]))
        if events:
            for event in events:
                description = f" — {event.description}" if event.description else ""
                story.append(Paragraph(f"{_text(event.timestamp)} s: {_text(event.type)}{_text(description)}", styles["Normal"]))
        else:
            story.append(Paragraph("No events recorded.", styles["Normal"]))
        if index < len(examinations):
            story.append(Spacer(1, 7 * mm))

    document.build(story)
    return output.getvalue()
