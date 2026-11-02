# MediMate: external usability and feasibility review

This material is offered **for research, demonstration and professional feedback only**; it does not claim NUH affiliation, independent clinical validation or patient readiness. Please use fictional names and medicine scenarios rather than actual patient records.

## Suggested review activities

1. Open the web app on macOS or Windows (see README) and create a fictional family profile.
2. Add and edit two fictional medication entries, including their prescribed times. Refresh and confirm they persist. The application does not provide or recommend doses.
3. Check that the daily calendar shows scheduled doses and that exporting the calendar reflects taken, missed and not-logged states.
4. With the included reference databases, try a known documented interaction such as sildenafil plus nitroglycerin and inspect the source, severity and description. **Do not use the result to make clinical decisions.**
5. Mark a *test* warning as reviewed (simulated consultation), refresh, verify it stays accessible under Reviewed interactions, and reopen it.
6. Change language among English, Tamil, Simplified Chinese and Malay; note awkward/ambiguous medical translations for independent review.
7. Test the medication Q&A interface using fictional general medicine questions (requires optional OpenAI API key). Check scope/refusals, uncertainty wording and source claims.
8. Test keyboard navigation, contrast and any screen-reader workflows as relevant.

## Questions for NUH clinical / patient usability reviewers

- Are risk, severity, source and uncertainty disclosures legible and understandable?
- Does acknowledgement of a warning risk conveying that the medicine combination is now safe?
- Is dose/adherence logging sufficiently obvious and resistant to mistakes?
- Does the family-profile design cause confusion about which person's medicines are shown?
- Are there clinically dangerous omissions, false positives, unsafe suggestions or misleading claims?
- What minimum clinical dataset and workflow validation would be needed for any controlled trial?
- Would review require an ethics/IRB, data-protection or medical-device regulatory assessment?

## Feedback format

Record task, expected behavior, observed behavior, severity (blocker/major/minor), screenshot without identifiers, device/browser, and whether it is reproducible. **Do not submit patient data or confidential hospital information to this repository.**

## Boundaries

No formal evaluation, clinical trial, prospective patient use, or NUH endorsement has been obtained. The app remains a **local-only, not patient-ready prototype**. Clinical and information-security approval would need to precede use with any real patients.

The repository is intended to contain both drug-reference SQLite files under `data/`. No separate database downloads are required. Live AI chat requires an authorised API key configured privately; never share private keys or patient records.
