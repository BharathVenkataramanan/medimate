# Third-party data, licences and acknowledgements

MediMate is a local research prototype. This file identifies third-party drug-reference material used by the project and documents changes made for local lookup. **It is not a licence for the MediMate application code**, nor is it a declaration that every third-party source has been cleared for unrestricted redistribution.

DDInter 2.0: bundled interaction database

- Creator/source: DDInter team, Computational Biology & Drug Design (CBDD) Group.
- Source: https://ddinter.scbdd.com/
- Official terms: https://ddinter.scbdd.com/terms/
- Licence: Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (**CC BY-NC-SA 4.0**).
- Licence text: https://creativecommons.org/licenses/by-nc-sa/4.0/
- File distributed by MediMate: `data/ddinter.sqlite3`.

Modification and redistribution notice. MediMate distributes a processed SQLite representation of DDInter drug-interaction data, not an unmodified DDInter download. The local database contains drug identifiers/names, a normalized name field for lookup, and interaction-pair records with recorded severity levels. Its main lookup tables are `drugs (id, name, norm)` and `pairs (a, b, level)`. MediMate uses these tables for local, read-only pair lookups via `ddinter_lookup.py`. Separately authored, source-linked clinical warnings and brand mappings are implemented in other project files; they should not be mistaken for original DDInter annotations.

The conversion to this application-specific SQLite layout and the normalization of lookup fields are changes to the source data's presentation/structure. This derived DDInter database is redistributed under CC BY-NC-SA 4.0, subject to the original licence, including:
- Attribution: credit the DDInter team, identify the source, link the licence and indicate modifications.
- NonCommercial: the licensed data must not be used or redistributed for commercial purposes without separately obtaining appropriate permission.
- ShareAlike: adaptations of the licensed DDInter material must be shared under the same or a permitted compatible licence.
- No endorsement or warranty: credit does not imply DDInter's approval of MediMate, and absence of a database match does not establish medication safety.


Provenance limitation: the repository contains the processed SQLite database but does not include a reproducible original DDInter-download-to-SQLite conversion script or an independently verified original source-file checksum. Those details would be needed for a more complete data-lineage record.

RxNorm: bundled medication identity catalogue

- Provider: US National Library of Medicine (NLM).
- Source: RxNorm Current Prescribable Content, October 5, 2026 monthly release, `RxNorm_full_prescribe_10052026.zip`.
- Official release listing: https://www.nlm.nih.gov/research/umls/rxnorm/docs/rxnormfiles.html
- Subset conditions: https://www.nlm.nih.gov/research/umls/rxnorm/docs/prescribe.html
- File distributed by MediMate: `data/rxnorm_catalog.sqlite3`.


Modifications: `rxnorm_graph.py` reads the release's `RXNCONSO.RRF` names/concepts and `RXNREL.RRF` relationships, keeps supported medication concepts, resolves source-backed product-to-ingredient relationships, and writes a compact local SQLite index. The resulting tables include `concepts`, `names`, `product_ingredients` and `metadata`. It is a project-specific derivative of a dated release, **not** a real-time NLM service or an official NLM product. Data may become outdated; no NLM endorsement is implied.

Other referenced medical-information sources

The following sources inform individual, source-linked brand mappings, medication warnings or optional online evidence checks. They are not represented as additional bundled wholesale databases.

- Singapore Ministry of Health, National Drug Formulary (NDF): https://www.ndf.gov.sg/ . `verified_medicines.py` includes short factual mappings, including Anarex, Norgesic and Cetagesic, with links to the relevant NDF product pages. 
- US National Library of Medicine, DailyMed: https://dailymed.nlm.nih.gov/ . Referenced for drug-label evidence and some brand/ingredient mappings.
- US Food and Drug Administration, openFDA and FDA drug information: https://open.fda.gov/apis/drug/label/ and https://www.fda.gov/drugs . Used for optional label lookups and source links.
- UK National Health Service and Specialist Pharmacy Service: https://www.nhs.uk/ and https://www.sps.nhs.uk/ . Individual articles are linked as evidence for selected warnings.



