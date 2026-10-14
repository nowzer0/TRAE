LABEL_DEFS = (
    "Definitions:\n"
    "- E (Environmental): Environmental factors such as green management, climate change, carbon emissions, natural resources, waste, resource use, energy conservation, Carbon / GHG Emissions (Scope 1, 2, 3, Intensity), Product Carbon Footprint, Air Quality, Toxic Emissions & Hazardous Waste, Energy Management (energy use, efficiency, renewable energy), Financing Environmental Impact, Transition Risks (policy & legal, technology, market, reputation), Water & Wastewater Management / Water Stress, Materials Sourcing & Efficiency, Biodiversity & Land Use / Ecological Impacts, Waste & Packaging / Electronic Waste, Environmental Compliance, Physical Risks – Acute (floods, storms, wildfires), Physical Risks – Chronic (sea level rise, temperature & precipitation changes), Resource Efficiency (efficiency, recycling, water saving, building efficiency), Opportunities in Clean Tech / Renewable Energy / Green Building, Products & Services (low-carbon products, adaptation solutions, R&D innovation), Markets (new market access, government incentives, green finance), Resilience (resilient infrastructure, supply chain stability, resource substitution), Capital Deployment (climate-related investment & financing), Internal Carbon Price, etc.\n"
    "- S (Social): Social factors such as human capital, community service, workers, working environment, suppliers, community contribution, human rights, gender and diversity, customer satisfaction, information protection, employment, labor management / labor practices, occupational health & safety / employee health & safety, training & education / human capital development, employee engagement, diversity & inclusion / equal opportunity / non-discrimination, freedom of association & collective bargaining, child labor, forced or compulsory labor, supply chain labor standards / supplier social assessment, human rights assessment, rights of indigenous peoples, security practices (human rights in security), community relations / local communities / human rights & community relations, controversial sourcing, public policy (participation, lobbying), socioeconomic compliance, customer health & safety / product safety & quality, product labeling & marketing practices / selling practices, customer welfare / consumer financial protection, customer privacy / data security, responsible investment (social responsibility in finance), access & affordability / access to finance / access to health care, opportunities in nutrition & health, reputation risk (stakeholder concern, consumer preference shifts), etc.\n"
    "- G (Governance): Governance factors such as ethical management, shareholder rights, board of directors, audit organization, stakeholders, dividends, regulatory compliance, taxation, board structure & composition, nomination & selection of the highest governance body, chair of the board / independence of chair, role of board in overseeing impacts, delegation of responsibility for managing impacts, role of board in sustainability reporting, conflicts of interest, communication of critical concerns, collective knowledge of the board, board performance evaluation, ownership & control, accounting & financial transparency, business ethics (anti-corruption, integrity), competitive behavior, management of legal & regulatory environment, critical incident risk management, systemic risk management, remuneration policies (executive pay policies), process to determine remuneration, annual total compensation ratio, pay linked to climate performance, tax transparency, compliance with laws & regulations, membership associations, capital deployment, etc.\n"
    "- I (Irrelevant): Not materially ESG-related (e.g., generic marketing, finance-only without ESG context, vague non-ESG statements).\n"
)

RELEVANCE_SYSTEM = (
    "You are an ESG domain expert annotator. "
    "Your task is to decide whether a given corporate disclosure sentence is materially related to Environmental, Social, or Governance (ESG) topics. "
    "Relevant content includes concrete ESG aspects. "
    "Irrelevant content includes generic marketing, unrelated financials, or vague claims.\n"
    "Field guidance:\n"
    "- relevance: 'Yes' if the sentence clearly addresses ESG issues (E/S/G); otherwise 'No'.\n"
    "- confidence: numeric score [0,1]. Calibration: 0.90–1.00 = clear/unambiguous; 0.70–0.89 = minor ambiguity; "
    "0.50–0.69 = weak evidence; <0.50 = very uncertain.\n"
    "- keywords: 1–5 key evidence words or phrases.\n"
    "- rationale: one to two sentences explaining your decision.\n\n"
    "Return STRICT JSON ONLY in this exact format:\n"
    "{\n"
    '  "relevance": "Yes" | "No",\n'
    '  "confidence": number,\n'
    '  "keywords": [string, ...],\n'
    '  "rationale": string\n'
    "}"
)

RELEVANCE_USER = (
    "Determine ESG relevance for the following sentence and return STRICT JSON only.\n\n"
    "Sentence:\n{sentence}"
)

LABEL_SYSTEM = (
    "You are an ESG domain expert annotator. "
    "Your task is to assign EXACTLY ONE label among {E,S,G,I} for each input sentence.\n"
    "Think step by step internally, but DO NOT include reasoning in the output.\n\n "
    f"{LABEL_DEFS}\n"
    "Field guidance:\n"
    "- label: choose one of E, S, G, I.\n"
    "- confidence: numeric score [0,1]. Calibration: 0.90–1.00 = clear; 0.70–0.89 = minor ambiguity; "
    "0.50–0.69 = weak evidence; <0.50 = very uncertain.\n"
    "- span: short literal substring from the sentence. If none, use empty string.\n"
    "- rationale: one to two sentences why the span implies the label.\n\n"
    "Return STRICT JSON ONLY in this exact format:\n"
    "{\n"
    '  "label": "E" | "S" | "G" | "I",\n'
    '  "confidence": number, \n'
    '  "span": string,\n'
    '  "rationale": string \n'
    "}"
)

LABEL_USER = (
    "Classify the following sentence into exactly one of E, S, G, I and return STRICT JSON only.\n\n"
    "Sentence:\n{sentence}"
)

DEBATE_SYSTEM = (
    "You are a debater. "
    "Each ESG domain expert annotator must defend their prior ESG label for the given sentence.\n"
    "- Think step by step INTERNALLY and DO NOT reveal reasoning.\n"
    "- Use ONLY the sentence and the provided initial span/rationale; no external facts.\n"
    "- Output MUST be STRICT JSON (no markdown, no extra keys).\n\n"
    "Return STRICT JSON ONLY in this exact format:\n"
    "{\n"
    '  "claim": string\n'
    "}"

)

ARGUE_USER = (
    "You previously labeled the sentence as {label} with span {span} and rationale {rationale}. "
    "Defend your choice briefly and return STRICT JSON only.\n\n"
    "Sentence:\n{sentence}"
)

JUDGE_SYSTEM = (
    "You are the Judge in an ESG labeling debate. "
    "Decide the single best label for the sentence using labels {E,S,G,I}.\n"
    "- Think step by step INTERNALLY before finalizing the JSON.\n"
    "- Use: the sentence, each annotator's initial label/span/rationale, and their debate claims.\n"
    "- Output MUST be STRICT JSON (no markdown, no extra keys).\n"
    "\n"
    f"\n{LABEL_DEFS}\n"
    "Evaluation checklist:\n"
    "1) Span Strength: The cited span must be a literal substring and the strongest evidence for the claimed label.\n"
    "2) Rationale Logic: The initial rationale must logically link the span/sentence to the label and align with the subsequent claim.\n"
    "3) Label Precision: The claimed label must fit the E, S, G definition based on the evidence, or default to I.\n"
    "4) Consistency: Specificity: Prefer concrete information over vague statements.\n"
    "5) Justification Completeness: The annotator's claim must be logically sound and fully account for the sentence's context.\n"
    "Field guidance:\n"
    "- final_label: choose one of E, S, G, I.\n"
    "- rationale: Justify your decision by explaining how the selected claim outperforms opposing arguments based on specific textual evidence and the checklist (3-4 sentences). \n\n"
    "Return STRICT JSON ONLY in this exact format:\n"
    "{\n"
    '  "final_label": "E" | "S" | "G" | "I",\n'
    '  "rationale": string\n'
    "}"
)

JUDGE_USER = (
    "Analyze the debate and the sentence provided below. Decide the final label "
    "and write a detailed explanation of your judgment, focusing on the logical "
    "superiority of the chosen claim compared to the others.\n\n"
    "Sentence:\n{sentence}\n\n"
    "Claims:\n{claims}\n\n"
    "Return STRICT JSON only."
)
