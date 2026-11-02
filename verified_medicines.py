


from __future__ import annotations
import re

SG_PRODUCTS = {
 'anarex': {
   'name':'Anarex tablets','ingredients':['orphenadrine','acetaminophen'],
   'display_ingredients':['orphenadrine citrate 35 mg','paracetamol 450 mg'],
   'source_url':'https://www.ndf.gov.sg/about-drugs/product-information/sin05584p/',
   'source':'Singapore National Drug Formulary (SIN05584P)',
 },
 'anarex tablets': {
   'name':'Anarex tablets','ingredients':['orphenadrine','acetaminophen'],
   'display_ingredients':['orphenadrine citrate 35 mg','paracetamol 450 mg'],
   'source_url':'https://www.ndf.gov.sg/about-drugs/product-information/sin05584p/',
   'source':'Singapore National Drug Formulary (SIN05584P)',
 },
 'norgesic': {
   'name':'Norgesic tablet','ingredients':['orphenadrine','acetaminophen'],
   'display_ingredients':['orphenadrine citrate 35 mg','paracetamol 450 mg'],
   'source_url':'https://www.ndf.gov.sg/about-drugs/product-information/sin05552p/',
   'source':'Singapore National Drug Formulary (SIN05552P)',
 },
 'norgesic tablet': {
   'name':'Norgesic tablet','ingredients':['orphenadrine','acetaminophen'],
   'display_ingredients':['orphenadrine citrate 35 mg','paracetamol 450 mg'],
   'source_url':'https://www.ndf.gov.sg/about-drugs/product-information/sin05552p/',
   'source':'Singapore National Drug Formulary (SIN05552P)',
 },
 'cetagesic': {
   'name':'Cetagesic tablet','ingredients':['orphenadrine','acetaminophen'],
   'display_ingredients':['orphenadrine citrate 25 mg','paracetamol 500 mg'],
   'source_url':'https://www.ndf.gov.sg/about-drugs/product-information/sin05771p/',
   'source':'Singapore National Drug Formulary (SIN05771P)',
 },
 'cetagesic tablet': {
   'name':'Cetagesic tablet','ingredients':['orphenadrine','acetaminophen'],
   'display_ingredients':['orphenadrine citrate 25 mg','paracetamol 500 mg'],
   'source_url':'https://www.ndf.gov.sg/about-drugs/product-information/sin05771p/',
   'source':'Singapore National Drug Formulary (SIN05771P)',
 },
}


LABEL_RULES = [
 {
   'a':'sildenafil','b':'nitroglycerin','level':'Contraindicated',
   'effects':'Sildenafil can greatly amplify the blood-pressure-lowering effect of nitroglycerin. This can cause severe hypotension, dizziness, fainting, or cardiovascular collapse.',
   'advice':'Do not use these together. Contact your prescriber or pharmacist urgently; if you have chest pain, fainting, or severe symptoms, seek emergency care and tell clinicians you take sildenafil.',
   'source':'FDA prescribing information: Viagra, contraindications and drug interactions',
   'source_url':'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=d905dc8d-917f-4ea3-a4ee-a1ecf6967d4e',
 },
 {
   'a':'tadalafil','b':'nitroglycerin','level':'Contraindicated',
   'effects':'Both medicines lower blood pressure; taking tadalafil with nitrate medicines can cause a dangerous drop in blood pressure, with dizziness or fainting.',
   'advice':'Do not combine them. Seek prompt advice from the treating clinician or pharmacist, and emergency help for serious symptoms.',
   'source':'FDA prescribing information: Cialis (nitrate contraindication)',
   'source_url':'https://www.dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=bcd8f8ab-81a2-4891-83db-24a0b0e25895',
 },
 {
   'a':'warfarin','b':'ibuprofen','level':'Major',
   'effects':'Ibuprofen can increase bleeding risk when used with warfarin, including gastrointestinal bleeding, serious bruising, or other internal bleeding.',
   'advice':'Ask a pharmacist or prescriber before taking both. Get urgent care for major bleeding, black stools or vomiting blood.',
   'source':'FDA prescribing information: warfarin sodium, drugs increasing bleeding risk',
   'source_url':'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=61ab23a7-bc67-4777-854a-bf43c788a69a',
 },
 {
   'a':'warfarin','b':'acetylsalicylic acid','level':'Major',
   'effects':'Aspirin and warfarin together can increase the chance of bleeding, including serious gastrointestinal bleeding.',
   'advice':'Confirm the combination with the prescriber. Do not change prescribed antithrombotic therapy without guidance.',
   'source':'FDA prescribing information: warfarin sodium, drugs increasing bleeding risk',
   'source_url':'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=61ab23a7-bc67-4777-854a-bf43c788a69a',
 },
 {
   'a':'simvastatin','b':'clarithromycin','level':'Contraindicated',
   'effects':'Clarithromycin can increase simvastatin exposure and cause muscle injury, including rhabdomyolysis, which can damage the kidneys.',
   'advice':'This combination is contraindicated in the product label. Contact the prescriber or pharmacist before co-administration.',
   'source':'FDA prescribing information: clarithromycin, contraindications and drug interactions',
   'source_url':'https://www.dailymed.nlm.nih.gov/dailymed/fda/fdaDrugXsl.cfm?setid=ba216276-b0bd-420a-9e0d-090bdfcc2460&type=display',
 },
]


NITRATES=('nitroglycerin','isosorbide mononitrate','isosorbide dinitrate')
PDE5_SOURCE={
    'sildenafil':('FDA prescribing information: Viagra','https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=d905dc8d-917f-4ea3-a4ee-a1ecf6967d4e'),
    'tadalafil':('FDA prescribing information: Cialis','https://www.dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=bcd8f8ab-81a2-4891-83db-24a0b0e25895'),
    'vardenafil':('FDA prescribing information: vardenafil','https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=57a0c163-a5e8-4c6e-a4ea-114cb2668407'),
    'avanafil':('FDA prescribing information: avanafil','https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=1d04e17d-7399-430a-a8bb-fa1912b155e9'),
}
RULE_INDEX = {frozenset((r['a'],r['b'])):r for r in LABEL_RULES}
for _pde5, (_source, _url) in PDE5_SOURCE.items():
    for _nitrate in NITRATES:
        _key=frozenset((_pde5,_nitrate))
        if _key not in RULE_INDEX:
            RULE_INDEX[_key]={
                'a':_pde5,'b':_nitrate,'level':'Contraindicated','code':'nitrate_pde5',
                'effects':f'{_pde5.title()} can amplify the blood-pressure-lowering effect of {_nitrate}, potentially causing severe low blood pressure, dizziness or fainting.',
                'advice':'Do not combine these medicines. Contact a prescriber or pharmacist promptly. Seek emergency care for severe symptoms or chest pain and disclose use of a PDE5 inhibitor.',
                'source':_source+' (nitrate contraindication)',
                'source_url':_url,
            }


BENZODIAZEPINES = ('diazepam', 'alprazolam', 'lorazepam', 'clonazepam', 'temazepam', 'midazolam')
OPIOIDS = ('oxycodone', 'hydrocodone', 'morphine', 'codeine', 'fentanyl', 'tramadol', 'hydromorphone')
for _benz in BENZODIAZEPINES:
    for _opioid in OPIOIDS:
        _key=frozenset((_benz,_opioid))
        if _key not in RULE_INDEX:
            RULE_INDEX[_key]={
                'a':_benz,'b':_opioid,'level':'Major','code':'opioid_benzodiazepine',
                'effects':'Combining an opioid with a benzodiazepine can cause extreme drowsiness, dangerously slow or stopped breathing, coma and death.',
                'advice':'Contact the prescribing clinician or pharmacist promptly to review this combination. Do not stop or change a prescribed medicine on your own. Call emergency services for very slow breathing, severe unresponsiveness or collapse.',
                'source':'FDA boxed warning: oxycodone, benzodiazepines and other CNS depressants',
                'source_url':'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=1bcddbe1-c453-43ec-a822-9e993b885a5f',
            }


CLINICAL_REFERENCE_RULES = [
    {
        'a': 'methotrexate', 'b': 'trimethoprim', 'level': 'Major',
        'effects': 'Trimethoprim with methotrexate can cause serious bone marrow suppression, potentially leading to infections, mouth ulcers, unexplained bruising or bleeding.',
        'advice': 'Do not start this combination without urgent review by the prescriber or pharmacist. NHS specialist guidance advises avoiding trimethoprim or co-trimoxazole with methotrexate.',
        'source': 'NHS Specialist Pharmacy Service: Managing interactions with methotrexate',
        'source_url': 'https://sps.nhs.uk/articles/managing-interactions-with-methotrexate/',
        'code': 'nhs_methotrexate_trimethoprim',
    },
    {
        'a': 'warfarin', 'b': 'trimethoprim', 'level': 'Major',
        'effects': 'Trimethoprim-containing antibiotic treatment, especially co-trimoxazole, can increase the anticoagulant effect of warfarin and raise the risk of bleeding.',
        'advice': 'Ask the prescriber or anticoagulation clinic to review the antibiotic and INR monitoring. Do not change warfarin independently.',
        'source': 'NHS: Taking trimethoprim with other medicines',
        'source_url': 'https://www.nhs.uk/medicines/trimethoprim/taking-trimethoprim-with-other-medicines-and-herbal-supplements/',
        'code': 'nhs_warfarin_trimethoprim',
    },
    {
        'a': 'linezolid', 'b': 'sertraline', 'level': 'Major',
        'effects': 'Linezolid and sertraline can trigger serotonin syndrome, which may cause agitation, fever, sweating, tremor and muscle rigidity.',
        'advice': 'Contact the treating clinician promptly; specialist risk assessment and monitoring are required if linezolid is necessary. Do not stop medication without guidance.',
        'source': 'DailyMed: Linezolid prescribing information, serotonin syndrome',
        'source_url': 'https://www.dailymed.nlm.nih.gov/dailymed/fda/fdaDrugXsl.cfm?setid=3e0d868d-f419-47e8-a3bc-41ececac468b&type=display',
        'code': 'fda_linezolid_sertraline',
    },
    {
        'a': 'linezolid', 'b': 'fluoxetine', 'level': 'Major',
        'effects': 'Linezolid and fluoxetine can cause serotonin syndrome; fluoxetine may remain active for weeks after the last dose.',
        'advice': 'Seek prescriber review before combining these medicines. Medication changes and monitoring require clinical supervision.',
        'source': 'DailyMed: Linezolid prescribing information, serotonin syndrome',
        'source_url': 'https://www.dailymed.nlm.nih.gov/dailymed/fda/fdaDrugXsl.cfm?setid=3e0d868d-f419-47e8-a3bc-41ececac468b&type=display',
        'code': 'fda_linezolid_fluoxetine',
    },
    {
        'a': 'linezolid', 'b': 'escitalopram', 'level': 'Major',
        'effects': 'Linezolid and escitalopram can cause serotonin syndrome, including agitation, high temperature, tremor or rigidity.',
        'advice': 'The prescribing clinician should review this combination and any required monitoring; do not adjust medicines without guidance.',
        'source': 'DailyMed: Linezolid prescribing information, serotonin syndrome',
        'source_url': 'https://www.dailymed.nlm.nih.gov/dailymed/fda/fdaDrugXsl.cfm?setid=3e0d868d-f419-47e8-a3bc-41ececac468b&type=display',
        'code': 'fda_linezolid_escitalopram',
    },
    {
        'a': 'lithium', 'b': 'ibuprofen', 'level': 'Major',
        'effects': 'Ibuprofen can reduce renal clearance of lithium, increase lithium blood concentrations and raise the risk of lithium toxicity.',
        'advice': 'Check with a prescriber or pharmacist before combining them; lithium blood-level and kidney-function monitoring may be needed.',
        'source': 'DailyMed: Lithium carbonate, clinically important interactions',
        'source_url': 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=df756a61-baf2-758a-e053-2a95a90a10ff',
        'code': 'fda_lithium_ibuprofen',
    },
    {
        'a': 'lithium', 'b': 'naproxen', 'level': 'Major',
        'effects': 'Naproxen can decrease lithium clearance and raise lithium concentrations, increasing the risk of toxicity.',
        'advice': 'Ask a clinician or pharmacist to review this combination and arrange lithium blood-level monitoring as appropriate.',
        'source': 'DailyMed: Lithium carbonate, clinically important interactions',
        'source_url': 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=df756a61-baf2-758a-e053-2a95a90a10ff',
        'code': 'fda_lithium_naproxen',
    },
    {
        'a': 'spironolactone', 'b': 'lisinopril', 'level': 'Major',
        'effects': 'Spironolactone and lisinopril can increase blood potassium; severe hyperkalemia may cause dangerous heart-rhythm problems.',
        'advice': 'Ask the prescriber to check whether potassium and kidney-function monitoring are required. Do not stop prescribed treatment independently.',
        'source': 'DailyMed: Spironolactone prescribing information, hyperkalemia',
        'source_url': 'https://www.dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=c23b6b9b-aec3-48a8-a518-76e4097f6479',
        'code': 'fda_spironolactone_lisinopril',
    },
    {
        'a': 'spironolactone', 'b': 'losartan', 'level': 'Major',
        'effects': 'Spironolactone and losartan can increase blood potassium; serious hyperkalemia may affect the heart.',
        'advice': 'Ask the prescribing clinician about potassium and renal-function monitoring, especially with kidney disease or dose changes.',
        'source': 'DailyMed: Spironolactone prescribing information, hyperkalemia',
        'source_url': 'https://www.dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=c23b6b9b-aec3-48a8-a518-76e4097f6479',
        'code': 'fda_spironolactone_losartan',
    },
]


for _source_name in ('lithium carbonate', 'lithium citrate', 'lithium cation'):
    for _other in ('ibuprofen', 'naproxen'):
        _base=next(r for r in CLINICAL_REFERENCE_RULES
                   if r['a']=='lithium' and r['b']==_other)
        RULE_INDEX.setdefault(frozenset((_source_name, _other)),
            dict(_base, a=_source_name, code=_base['code'] + '_exact_' + _source_name.replace(' ', '_')))


for _clinical in CLINICAL_REFERENCE_RULES:
    RULE_INDEX.setdefault(frozenset((_clinical['a'], _clinical['b'])), _clinical)


DUPLICATE_ACETAMINOPHEN = {
 'level':'Review duplicate ingredient',
 'effects':'Both medicines contain paracetamol (acetaminophen). Taking overlapping products can accidentally exceed the intended dose and cause serious liver injury.',
 'advice':'Check the total paracetamol from all products with a pharmacist. Do not take extra doses to compensate for missed doses.',
 'source':'US FDA: Avoid taking more than one acetaminophen-containing product',
 'source_url':'https://www.fda.gov/drugs/safe-use-over-counter-pain-relievers-and-fever-reducers/acetaminophen',
}

def clean_key(value: str) -> str:
    value=re.sub(r'\s+', ' ',str(value or '').strip().casefold())
    return value

def sg_match(value: str) -> dict | None:


    return SG_PRODUCTS.get(clean_key(value))


FOOD_SOURCE = 'https://www.fda.gov/consumers/consumer-updates/grapefruit-juice-and-some-drugs-dont-mix'
FOOD_PRODUCTS = {
    'grapefruit juice': 'grapefruit',
    'grapefruit': 'grapefruit',
    'fresh grapefruit': 'grapefruit',
}


GRAPEFRUIT_DRUGS = {
    'simvastatin': ('Some grapefruit products can increase simvastatin exposure, raising the risk of muscle injury (including rhabdomyolysis) and liver problems.',
                    'Ask a pharmacist about avoiding grapefruit while using this medicine.'),
    'atorvastatin': ('Grapefruit may increase atorvastatin exposure, increasing the possibility of side effects such as muscle injury.',
                     'Check your product instructions and ask a pharmacist what amount, if any, is appropriate.'),
    'nifedipine': ('Grapefruit can increase exposure to some nifedipine products, potentially causing excessive blood-pressure lowering and dizziness.',
                   'Ask your pharmacist whether grapefruit should be avoided with your exact formulation.'),
    'cyclosporine': ('Grapefruit can increase cyclosporine exposure, raising the risk of adverse effects.',
                     'Consult the transplant team or pharmacist before consuming grapefruit.'),
    'buspirone': ('Grapefruit may increase buspirone exposure, potentially worsening dizziness and drowsiness.',
                  'Ask your pharmacist or prescriber about avoiding grapefruit.'),
    'budesonide': ('Grapefruit can raise exposure to certain orally administered budesonide products, increasing the possibility of corticosteroid side effects.',
                   'Check your exact product and ask the pharmacist whether grapefruit should be avoided.'),
    'amiodarone': ('Grapefruit can increase amiodarone exposure and may increase the risk of medication side effects.',
                   'Ask the prescribing clinician or pharmacist to review this combination.'),
    'fexofenadine': ('Grapefruit juice may REDUCE fexofenadine absorption, so the medicine may work less effectively.',
                     'Take fexofenadine with water rather than fruit juice unless your clinician advises otherwise.'),
}
for _ingredient, (_effects, _advice) in GRAPEFRUIT_DRUGS.items():
    RULE_INDEX[frozenset(('grapefruit', _ingredient))] = {
        'a': 'grapefruit', 'b': _ingredient, 'level': 'Food–medicine interaction',
        'code': 'grapefruit_' + _ingredient,
        'effects': _effects, 'advice': _advice,
        'source': 'US FDA: Grapefruit Juice and Some Drugs Don’t Mix',
        'source_url': FOOD_SOURCE,
    }


RXNORM_CANONICAL = {
    'paracetamol': 'acetaminophen',
    'acetylsalicylic acid': 'acetylsalicylic acid',
    'sildenafil citrate': 'sildenafil',
    'diazepam': 'diazepam',
}
