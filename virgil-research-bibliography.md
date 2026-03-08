# Virgil — Research Papers Bibliography

> AI Content Generation, Personalization & Writing Assistance
> Compiled: 2024–2026 | Relevance: Virgil AI Writing Platform

-----

## 1. Writing Style Transfer & Voice Preservation

### 1.1 Panza: Design and Analysis of a Fully-Local Personalized Text Writing Assistant

- **Autori:** Armand Mihai Nicolicioiu et al.
- **Venue:** ICLR 2025 Workshop on Foundation Models in the Wild
- **Rok:** 2025
- **Kľúčový nález:** PEFT + RAG na user emailoch. Menej ako 100 emailových samples stačí na presvedčivú imitáciu štýlu podľa MAUVE metrík a human judgments.
- **Relevancia pre Virgil:** Najbližší akademický analog Virgil architektúry. Validuje minimalistický onboarding — scale exemplárov nemusí byť veľký.
- **Linky:**
  - [arXiv 2407.10994](https://arxiv.org/abs/2407.10994)
  - [OpenReview (ICLR Workshop)](https://openreview.net/forum?id=gsr3t360Xy)
  - [PDF](https://openreview.net/pdf?id=gsr3t360Xy)

-----

### 1.2 Personalized Text Generation with Contrastive Activation Steering

- **Autori:** Yuting Liu et al.
- **Venue:** ACL 2025 (long paper)
- **Rok:** 2025
- **Kľúčový nález:** Naučia sa "style vectors" v activation space kontrastovaním user-authored vs. neutrálnych textov. +8% relatívne zlepšenie, 1700× menšie úložisko než PEFT per-user adaptery. Separuje štýl od obsahu — style informácia je sústredená v middle–late vrstvách.
- **Relevancia pre Virgil:** Architektonicky zaujímavé pre Phase 3 — style nie ako prompt text, ale ako latentný vektor.
- **Linky:**
  - [ACL Anthology](https://aclanthology.org/2025.acl-long.353.pdf)
  - [arXiv 2503.05213](http://arxiv.org/pdf/2503.05213.pdf)

-----

### 1.3 LLMs Still Struggle to Imitate the Implicit Writing Styles of Everyday Authors

- **Autori:** viacero autorov
- **Venue:** Findings of EMNLP 2025
- **Rok:** 2025
- **Kľúčový nález:** Benchmark 40 000+ generácií, 400+ reálnych autorov. Few-shot prompting funguje pre štruktúrované domény (news, email), ale zlyháva pre neformálne blog/forum štýly. Výzva pre predpoklad, že pár exemplárov stačí.
- **Relevancia pre Virgil:** Priamo relevantné — Virgil cieli práve na bloggery. Potvrdzuje nutnosť hybridného prístupu: exemplars + style summary + raw thinking input.
- **Linky:**
  - [ACL Anthology](https://aclanthology.org/2025.findings-emnlp.532/)
  - [arXiv 2509.14543](https://arxiv.org/abs/2509.14543)
  - [PDF](https://aclanthology.org/2025.findings-emnlp.532.pdf)

-----

### 1.4 Improving RAG for Personalization with Author Features and Contrastive Examples

- **Autori:** viacero autorov
- **Venue:** ECIR 2025 / arXiv
- **Rok:** 2025
- **Kľúčový nález:** Contrastive examples (dokumenty od iných autorov) + author features (frequently used words, sentiment polarity, dependency patterns) = +15% zlepšenie oproti baseline RAG. 1 veta o frequently used words výrazne zlepšuje výsledky.
- **Relevancia pre Virgil:** Pre Scriptorium RAG implementáciu — netreba len podobné dokumenty, ale aj kontrastné.
- **Linky:**
  - [arXiv 2504.08745](https://arxiv.org/html/2504.08745)
  - [ACM DL](https://dl.acm.org/doi/10.1007/978-3-031-88714-7_40)

-----

### 1.5 New Study Reveals That AI Cannot Fully Write Like a Human

- **Autori:** James O'Sullivan et al. (University College Cork)
- **Venue:** Humanities and Social Sciences Communications
- **Rok:** December 2025
- **Kľúčový nález:** AI-generovaný text vykazuje konzistentné, uniformné štylistické vzorce rozlíšiteľné od ľudskej prózy. Ľudskí autori majú výrazne väčšiu štylistickú diverzitu. GPT-4 nereproduktuje variabilitu ľudského písania.
- **Relevancia pre Virgil:** Potvrdzuje core value proposition — grounding generation v genuine ľudskom obsahu (raw notes, exemplars) rieši homogenizáciu na input-level.
- **Linky:**
  - [TechXplore](https://techxplore.com/news/2025-12-reveals-ai-fully-human.html)

-----

## 2. Personalizácia, Preference Learning & Cold Start

### 2.1 Personalize Your LLM: Fake It Then Align It (CHAMELEON)

- **Autori:** Yijing Zhang et al.
- **Venue:** arXiv (under review)
- **Rok:** 2025
- **Kľúčový nález:** Self-generuje syntetické preference data z jedinej historickej ukážky per user → representation editing pri inference. +40% nad baselines na LaMP, bez fine-tuningu.
- **Relevancia pre Virgil:** 🔑 Priamo aplikovateľné na cold start problém. Bootstrap štýlového profilu z 1 článku + interview.
- **Linky:**
  - [arXiv 2503.01048](http://arxiv.org/pdf/2503.01048.pdf)

-----

### 2.2 Democratizing Large Language Models via Personalized Parameter-Efficient Fine-Tuning (OPPU)

- **Autori:** Zhaoxuan Tan et al.
- **Venue:** arXiv 2402.04401
- **Rok:** 2025
- **Kľúčový nález:** One-PEFT-Per-User — malé per-user PEFT moduly ukladajú user-specific vzorce. Výrazne lacnejší než full fine-tuning. Outperformuje group-level a prompt-only personalizáciu.
- **Relevancia pre Virgil:** Phase 3 roadmap item — per-user LoRA fine-tuning ako technicky reálny differenciátor.
- **Linky:**
  - [arXiv 2402.04401](http://arxiv.org/pdf/2402.04401.pdf)

-----

### 2.3 ExPerT: Effective and Explainable Evaluation of Personalized Long-Form Text Generation

- **Autori:** Alireza Salemi, Julian Killingback, Hamed Zamani et al.
- **Venue:** Findings of ACL 2025
- **Rok:** 2025
- **Kľúčový nález:** LLM-based evaluačný framework dekomponuje generácie na "atomic aspects" a hodnotí content + style alignment s user profilmi. Citlivejší a vysvetliteľnejší než BLEU/ROUGE pre personalizovanú generáciu.
- **Relevancia pre Virgil:** Validuje star rating systém — potvrdzuje že automatické metriky sú nedostatočné. Inšpiruje internal evaluation quality gates.
- **Linky:**
  - [ACL Anthology](https://aclanthology.org/2025.findings-acl.900.pdf)

-----

### 2.4 From Guessing to Asking: Resolving the Persona Knowledge Gap in LLMs (CPER)

- **Autori:** Alina Asisof et al.
- **Venue:** NAACL 2025 Student Research Workshop
- **Rok:** 2025
- **Kľúčový nález:** Detekuje persona knowledge gap → proaktívne elicituje preferencie. Human A/B: odpovede preferované o 42% (CCPE-M) a 27% (ESConv) viac, špeciálne v dlhých konverzáciách (12+ turns).
- **Relevancia pre Virgil:** Architektonický vzor pre session writing flow — keď AI nevie kontext pisateľa, pýtaj sa cielenou otázkou namiesto hádania.
- **Linky:**
  - [arXiv 2503.12556](https://arxiv.org/abs/2503.12556)
  - [ACL Anthology](https://aclanthology.org/2025.naacl-srw.42)

-----

### 2.5 Few-shot Personalization of LLMs with Mis-aligned Responses (Fermi)

- **Autori:** Jaehyung Kim et al.
- **Venue:** arXiv 2406.18678
- **Rok:** 2025
- **Kľúčový nález:** Naučí sa personalizované prompty per user progresívnym zlepšovaním cez LLM, na základe user profile + niekoľkých príkladov predchádzajúcich názorov. Incorporuje kontext mis-aligned odpovedí.
- **Relevancia pre Virgil:** Iteratívne zlepšovanie style summary cez feedback loop.
- **Linky:**
  - [arXiv 2406.18678](https://arxiv.org/abs/2406.18678)

-----

### 2.6 Personalization of Large Language Models: A Survey

- **Autori:** viacero autorov
- **Venue:** arXiv 2411.00027
- **Rok:** 2025 (aktualizovaný)
- **Kľúčový nález:** Komplexný prehľad personalizácie LLM — (a) personalized text generation, (b) downstream task personalization. Predpovedá konvergenciu oboch prístupov.
- **Relevancia pre Virgil:** Orientačný dokument pre celkový landscape.
- **Linky:**
  - [arXiv 2411.00027](https://arxiv.org/html/2411.00027v3)

-----

### 2.7 A Survey of Personalization: From RAG to Agent

- **Autori:** viacero autorov
- **Venue:** arXiv 2504.10147
- **Rok:** 2025
- **Kľúčový nález:** Prehľad metód personalizácie — sparse/dense retrieval, prompt summarization, agent-based prístupy. EMG-RAG: kombinuje editable memory graphs s RAG pre dynamické user profily.
- **Relevancia pre Virgil:** Mapuje celý priestor riešení.
- **Linky:**
  - [arXiv 2504.10147](https://arxiv.org/html/2504.10147v1)

-----

## 3. Context Isolation & Multi-Persona AI

### 3.1 PALACE: A Persona-Aware LLM-Enhanced Framework for Multi-Session Personalized Dialogue Generation

- **Autori:** Dongshuo Liu et al.
- **Venue:** Findings of ACL 2025
- **Rok:** 2025
- **Kľúčový nález:** Topic-aware memory bank + persona commonsense graph + VAE-LoRA. Retrieves iba štrukturálne relevantné histórie a persona fakty. Výrazne lepšia persona konzistencia oproti baseline.
- **Relevancia pre Virgil:** Potvrdzuje profile isolation architektúru. Graph-based persona reprezentácia pre cross-session konzistenciu.
- **Linky:**
  - [ACL Anthology](https://aclanthology.org/2025.findings-acl.5/)
  - [PDF](https://aclanthology.org/2025.findings-acl.5.pdf)

-----

### 3.2 Post Persona Alignment for Multi-Session Dialogue Generation (PPA)

- **Autori:** Yi-Pei Chen et al.
- **Venue:** Findings of EMNLP 2025
- **Rok:** 2025
- **Kľúčový nález:** Reversal pipeline: najprv generuj bez persony → retrieve persona memory → refine draft. Lepšia konzistencia, diverzita a persona relevancia než pre-alignment.
- **Relevancia pre Virgil:** 🔑 Konkrétna implementačná technika: (1) draft bez profile → (2) retriev exemplars → (3) align/refine. Znižuje style hallucination.
- **Linky:**
  - [ACL Anthology](https://aclanthology.org/2025.findings-emnlp.1098/)
  - [arXiv 2506.11857](https://arxiv.org/html/2506.11857v1)

-----

### 3.3 Disentangling Multi-task Interference for Training-free Model Merging (NeuroMerging)

- **Autori:** Zitao Fang et al.
- **Venue:** EMNLP 2025 main
- **Rok:** 2025
- **Kľúčový nález:** Dekomponuje task-specific reprezentácie do komplementárnych neurónových subpriestanov pre riešenie multi-task interferencie.
- **Relevancia pre Virgil:** Vysvetľuje prečo cross-profile contamination nastáva v base LLM na model-level.
- **Linky:**
  - [ACL Anthology](https://aclanthology.org/2025.emnlp-main.793/)
  - [arXiv 2503.05320](https://arxiv.org/abs/2503.05320)

-----

## 4. Human–AI Collaborative Writing

### 4.1 Prototypical Human-AI Collaboration Behaviors from LLM-Assisted Writing in the Wild

- **Autori:** Xudong Gao et al. (Sheshera Mysore et al.)
- **Venue:** EMNLP 2025 main
- **Rok:** 2025
- **Kľúčový nález:** Analýza real-world usage logs LLM writing assistant. Malá sada opakujúcich sa "collaboration prototypes" (heavy drafting vs. light polishing). Určité mixed-initiative vzorce korelujú s vyššou kvalitou revízií a nižším editing effort.
- **Relevancia pre Virgil:** Empirické dáta o tom ako ľudia skutočne používajú AI writing assistants.
- **Linky:**
  - [ACL Anthology](https://aclanthology.org/2025.emnlp-main.852.pdf)

-----

### 4.2 Shaping Human-AI Collaboration: Varied Scaffolding Levels in Co-writing with Language Models

- **Autori:** viacero autorov
- **Venue:** CHI 2024
- **Rok:** 2024
- **Kľúčový nález:** N=131. Low scaffolding (next-sentence) = žiadne zlepšenie kvality. High scaffolding (next-paragraph) = signifikantné zlepšenia, špeciálne pre ne-pravidelných pisateľov. Mierne zníženie text ownership.
- **Relevancia pre Virgil:** Paragraph-level suggestions > sentence-level. Thinking-first prístup adresuje ownership problém.
- **Linky:**
  - [ACM DL](https://dl.acm.org/doi/10.1145/3613904.3642134)
  - [arXiv 2402.11723](https://arxiv.org/pdf/2402.11723.pdf)

-----

### 4.3 Corporate Communication Companion (CCC): An LLM-empowered Writing Assistant for Workplace Social Media

- **Autori:** viacero autorov
- **Venue:** arXiv 2405.04656
- **Rok:** 2024
- **Kľúčový nález:** Systém rozkladajúci písanie na outline + edit fázy hodnotený výrazne engaging-nejšie a collaborative-jšie. Posts generované cez CCC vnímané ako kompletnejšie a unikátnejšie.
- **Relevancia pre Virgil:** Decomposed writing flow (outline → expand → refine) je výskumom potvrdenou lepšou UX pattern. Validuje session-based design.
- **Linky:**
  - [arXiv 2405.04656](https://arxiv.org/html/2405.04656v1)

-----

### 4.4 Cognitive Load Scale for AI-Assisted L2 Writing (CL-AI-L2W)

- **Autori:** Guangyuan Yao & Lingxi Fan
- **Venue:** Frontiers in Psychology
- **Rok:** 2025
- **Kľúčový nález:** Validovaná 18-položková, 4-faktorová škála kognitívnej záťaže (Prompt Management, Critical Evaluation, Integrative Synthesis, Authorial Core Processing). Silné korelácie s writing anxiety a self-efficacy.
- **Relevancia pre Virgil:** Framework pre meranie cognitive load v onboardingu a session writing.
- **Linky:**
  - [Frontiers in Psychology](https://www.frontiersin.org/articles/10.3389/fpsyg.2025.1666974/full)
  - [PubMed](https://pubmed.ncbi.nlm.nih.gov/41245310/)

-----

## 5. Selective Text Editing

### 5.1 FineEdit: Bridging the Editing Gap in LLMs for Precise and Targeted Text Modifications

- **Autori:** Yiming Zeng et al.
- **Venue:** Findings of EMNLP 2025 / arXiv 2502.13358
- **Rok:** 2025
- **Kľúčový nález:** InstrEditBench (~20k kontrolovaných edit taskov: Wiki, LaTeX, kód, DSL). FineEdit: +10% presnosť oproti silným baselines, minimalizuje unintended zmeny v non-edited regiónoch.
- **Relevancia pre Virgil:** 🔑 Priamo relevantné pre selective editing feature — najväčší technical challenge. InstrEditBench metriky ako evaluation framework pre block-based editing.
- **Linky:**
  - [ACL Anthology](https://aclanthology.org/anthology-files/anthology-files/pdf/findings/2025.findings-emnlp.118v2.pdf)
  - [arXiv 2502.13358](http://arxiv.org/pdf/2502.13358.pdf)

-----

### 5.2 HyperEdit: Unlocking Instruction-based Text Editing in LLMs via Hypernetworks

- **Autori:** Yiming Zeng et al.
- **Venue:** arXiv 2602.08676 (2026)
- **Rok:** 2026
- **Kľúčový nález:** Hypernetwork generuje dynamic low-rank adaptery per editing instruction. Nové metriky: **Diff-BLEU, Diff-ROUGE-L** (meranie zmien vs. nezmenených regiónov). Výrazne menej spurious edits.
- **Relevancia pre Virgil:** 🔑 Diff-BLEU/Diff-ROUGE-L sú presne metriky potrebné pre evaluáciu block editov v Virgil — čo sa zmenilo vs. čo ostalo.
- **Linky:**
  - [arXiv 2512.12544 / 2602.08676](https://arxiv.org/html/2512.12544v1)

-----

### 5.3 Targeted Source Text Editing for Machine Translation

- **Autori:** Katsuhito Sudoh et al.
- **Venue:** WMT 2025
- **Rok:** 2025
- **Kľúčový nález:** Kombinácia span-level quality estimation a word alignment pre identifikáciu problematických spans → LLM edituje iba tie. Zlepšenie naprieč 8 MT systémami a 4 jazykovými dvojicami.
- **Relevancia pre Virgil:** Span-level quality estimation vzor aplikovateľný pre detekciu blokov vyžadujúcich úpravu.
- **Linky:**
  - [ACL Anthology](https://aclanthology.org/2025.wmt-1.12)

-----

## 6. Quality-Based Learning (LIMA Principle — Extensions)

### 6.1 NILE: Internal Consistency Alignment in Large Language Models

- **Autori:** Minda Hu et al.
- **Venue:** EMNLP 2025 main
- **Rok:** 2025
- **Kľúčový nález:** 3-stage pipeline: Internal Knowledge Extraction → Knowledge-aware Sample Revision → Internal Consistency Filtering. +66.6% na Arena-Hard, +68.5% AlpacaEval V2. Príliš málo aj príliš veľa konzistencie škodí.
- **Relevancia pre Virgil:** Validuje quality gate (len 4-5★ articles feed style learning). Optimálna variabilita, nie len maximálna kvalita.
- **Linky:**
  - [ACL Anthology](https://aclanthology.org/2025.emnlp-main.412/)
  - [arXiv 2412.16686](https://arxiv.org/abs/2412.16686)

-----

### 6.2 Aligning Instruction Tuning with Pre-training (AITP)

- **Autori:** Yiming Liang et al.
- **Venue:** arXiv 2501.09368
- **Rok:** 2025
- **Kľúčový nález:** Identifikuje under-covered regióny pre-training distribúcie, prepíše ich do instruction-response párov → zlepšenie o niekoľko bodov naprieč 8 benchmarkami.
- **Relevancia pre Virgil:** Inšpiratívne pre style drift prevención: ak user píše v doméne ktorú model pozná zle, explicitne to identifikovať.
- **Linky:**
  - [arXiv 2501.09368](https://arxiv.org/abs/2501.09368)

-----

### 6.3 LIMA: Less Is More for Alignment

- **Autori:** Chunting Zhou et al. (Meta AI)
- **Venue:** NeurIPS 2023
- **Rok:** 2023
- **Kľúčový nález:** 1000 starostlivo vybraných príkladov pre SFT prekonáva modely trénované na 50k+ príkladoch. Kvalita dát > množstvo dát.
- **Relevancia pre Virgil:** Foundational paper pre "learn only from 4-5★ articles" princíp.
- **Linky:**
  - [NeurIPS Proceedings](https://proceedings.neurips.cc/paper_files/paper/2023/file/ac662d74829e4407ce1d126477f4a03a-Paper-Conference.pdf)

-----

## 7. RAG — Style vs. Facts Separation

### 7.1 PEARL: Personalizing Large Language Model Writing Assistants with Generation-Calibrated Retrievers

- **Autori:** Sheshera Mysore et al.
- **Venue:** CustomNLP4U @ EMNLP 2024
- **Rok:** 2023/2024
- **Kľúčový nález:** Generation-calibrated retrievers pre personalizáciu LLM writing assistants cez historické user dáta.
- **Relevancia pre Virgil:** Priamy predchodca Virgil RAG architektúry.
- **Linky:**
  - [arXiv 2311.09180](https://arxiv.org/abs/2311.09180)
  - [ACL Anthology](https://aclanthology.org/2024.customnlp4u-1.16.pdf)

-----

### 7.2 Personalizing Large Language Models using Retrieval Augmented Generation and Knowledge Graph

- **Autori:** Deeksha Prahlad et al.
- **Venue:** WWW 2025
- **Rok:** 2025
- **Kľúčový nález:** Personal Knowledge Graph ako retrieval backend pre RAG. +61.11% BLEU improvement, ~8.9% rýchlejší response time vs. raw personal text.
- **Relevancia pre Virgil:** Pre Scriptorium — štruktúrovaná KG reprezentácia domain knowledge môže byť lepšia ako raw document embedding.
- **Linky:**
  - [arXiv 2505.09945](https://arxiv.org/abs/2505.09945v1)
  - [YouTube prezentácia](https://www.youtube.com/watch?v=lwW8FWrzwzM)

-----

### 7.3 Retrieval Augmented Generation with Collaborative Filtering for Personalized Text Generation (CFRAG)

- **Autori:** viacero autorov
- **Venue:** arXiv 2504.05731
- **Rok:** 2025
- **Kľúčový nález:** Adaptuje collaborative filtering do RAG pre personalizáciu. Trénuje user embeddings cez contrastive learning, retrieves dokumenty na základe user preferencií (nie len semantic relevance).
- **Relevancia pre Virgil:** Inšpiruje budúci cross-profile recommendation v Virgil (napr. "pisatelia ako ty používajú tieto exempláre").
- **Linky:**
  - [arXiv 2504.05731](https://arxiv.org/html/2504.05731)

-----

### 7.4 Meetalk: Retrieval-Augmented and Adaptively Personalized Meeting Assistant

- **Autori:** viacero autorov
- **Venue:** Findings of ACL 2025 (KnowLLM workshop)
- **Rok:** 2025
- **Kľúčový nález:** Separátne retrieval konfigurácie pre style information vs. factual grounding v jednom systéme.
- **Relevancia pre Virgil:** Potvrdzuje dizajnovú voľbu — Style Summary (profil) a Scriptorium (domain knowledge) musia byť oddelené retrieval paths.
- **Linky:**
  - [ACL Anthology](https://aclanthology.org/2025.knowllm-1.9.pdf)

-----

## 8. User Onboarding & Friction Reduction

### 8.1 How to Onboard Users to Conversational Agent Interactions — A Framework and Evaluation

- **Autori:** Alina Asisof, Marcia Nißen, Florian von Wangenheim
- **Venue:** AMCIS 2025
- **Rok:** 2025
- **Kľúčový nález:** 85% users engaguje s onboardingom. Depth predikuje ease-of-use, breadth predikuje trust. Oba spolu predikujú satisfaction.
- **Relevancia pre Virgil:** Validuje "generate first, interview second" — depth (kvalita prvého zážitku) > breadth (počet otázok zodpovedaných pred prvým výstupom).
- **Linky:**
  - [AMCIS 2025 Proceedings](https://aisel.aisnet.org/amcis2025/sig_hci/sig_hci/4/)

-----

### 8.2 Onboarding for AI Features: Reducing Friction at the First Use

- **Autori:** (neuvedený)
- **Venue:** International Journal of Computer Applications in AI, vol. 6(2)
- **Rok:** 2025
- **Kľúčový nález:** Framework pre onboarding AI features: transparency, user control, stepwise disclosure. Case studies (Siri, Alexa, Amazon) — progressive feature release a clear explanations znižujú cognitive overload.
- **Relevancia pre Virgil:** Progressive disclosure vzor pre interview wizard.
- **Linky:**
  - [IJCAI Journal](https://www.computersciencejournals.com/ijcai/archives/2025.v6.i2.E.227)
  - [PDF](https://www.computersciencejournals.com/ijcai/archives/2025/vol6issue2/PartE/6-2-82-363.pdf)

-----

### 8.3 Conversation Progress Guide: UI System for Enhancing Self-Efficacy in Conversational AI

- **Autori:** Daeun Jeong et al.
- **Venue:** arXiv 2501.12001 (HCI venue)
- **Rok:** 2025
- **Kľúčový nález:** Progress-visualization UI pre chat systémy zlepšuje self-efficacy a engagement. Znižuje early-stage confusion a dropout v AI onboarding flows.
- **Relevancia pre Virgil:** 🔑 Konkrétny UX pattern — vizuálny progress indicator počas interview wizard môže adresovať 40-55% dropout problém.
- **Linky:**
  - [arXiv 2501.12001](https://arxiv.org/html/2501.12001v1)

-----

## 9. Autorský Štýl — Stylometry & Authorship

### 9.1 Personalized Image Generation from an Author's Writing Style (AWS Pipeline)

- **Autori:** viacero autorov
- **Venue:** arXiv 2507.03313
- **Rok:** 2025
- **Kľúčový nález:** Author Writing Sheets (AWS) — štruktúrované zhrnutia literárnych charakteristík autora — ako input do Claude 3.7 Sonnet. Mean style match: 4.08/5 pri human evaluation (N=49 autorov).
- **Relevancia pre Virgil:** Virgil Style Summaries sú v podstate AWS. Výskum priamo potvrdzuje approach a dokonca používa Claude pre interpretáciu AWS.
- **Linky:**
  - [arXiv 2507.03313](https://arxiv.org/html/2507.03313)

-----

### 9.2 Exploring the Boundaries of Authorship: AI-generated Text vs. Human Academic Writing

- **Autori:** Amirjalili F., Neysani M., Nikbakht A.
- **Venue:** Frontiers in Education
- **Rok:** 2024
- **Kľúčový nález:** AI-generovaný text má ťažkosti s preservovaním recognizable a unique authorial presence. Type-token ratio indikuje väčšiu lexikálnu diverzitu u ľudských autorov.
- **Relevancia pre Virgil:** Empirická evidencia prečo je Virgil "guide, not generator" prístup dôležitý.
- **Linky:**
  - [Frontiers in Education](https://www.frontiersin.org/journals/education/articles/10.3389/feduc.2024.1347421/full)

-----

## 10. Evaluácia Štýlovej Personalizácie

### 10.1 Evaluating Style-Personalized Text Generation: Challenges and Directions

- **Autori:** viacero autorov
- **Venue:** arXiv 2508.06374
- **Rok:** 2025
- **Kľúčový nález:** Vyhodnocuje open-source modely (Ministral, Llama, Qwen, DeepSeek) aj closed-source (o4-mini, gpt-4.1) pre style personalizáciu. Navrhuje ensemble evaluačné metriky.
- **Relevancia pre Virgil:** Benchmark pre porovnanie modelov pre style-personalized generation.
- **Linky:**
  - [arXiv 2508.06374](https://arxiv.org/html/2508.06374)

-----

## 11. Pozičné & Prehľadové Papery

### 11.1 Position: It's Time to Act on the Risk of Efficient Personalized Text Generation

- **Autori:** viacero autorov
- **Venue:** arXiv 2502.06560
- **Rok:** 2025
- **Kľúčový nález:** Fine-tuning v súčasnosti zlepšuje výsledky vo väčšej miere ako samotný RAG. Per-user LoRA je technicky reálny (RTX4080, niekoľko hodín). Aktuálne metriky nie sú dostatočne indikatívne pre skutočnú kvalitu.
- **Relevancia pre Virgil:** Roadmap validácia: RAG now, per-user fine-tuning later.
- **Linky:**
  - [arXiv 2502.06560](https://arxiv.org/html/2502.06560v2)

-----

### 11.2 Controllable Text Generation for Large Language Models: A Survey

- **Autori:** viacero autorov
- **Venue:** arXiv 2408.12599
- **Rok:** 2024
- **Kľúčový nález:** Komplexný prehľad techník pre controllable text generation — stylistic adherence, thematic consistency, safety.
- **Relevancia pre Virgil:** Orientačný dokument pre architektonické rozhodnutia.
- **Linky:**
  - [arXiv 2408.12599](https://arxiv.org/abs/2408.12599)
  - [GitHub (living repo)](https://github.com/IAAR-Shanghai/CTGSurvey)

-----

## 12. Multilingual Style Transfer & Cross-Lingual Personalization

### 12.1 mStyleDistance: Multilingual Style Embeddings and their Evaluation

- **Autori:** Justin Qiu, Jiacheng Zhu, Ajay Patel, Marianna Apidianaki, Chris Callison-Burch
- **Venue:** Findings of ACL 2025
- **Rok:** 2025
- **Kľúčový nález:** Prvý multilingválny style embedding model trénovaný cez contrastive learning na syntetických dátach naprieč 9 jazykmi (arabčina, nemčina, španielčina, francúzština, hindčina, japončina, kórejčina, ruština, čínština). Embeddingy prekonávajú existujúce modely na multilingválnych style benchmarkoch a generalizujú na nepredtým videné jazyky — umožňujú cross-lingual authorship verification a style comparison.
- **Relevancia pre Virgil:** 🔑 Kľúčový building block pre multilingválny Virgil. Language-agnostic style embeddingy umožnia style matching a voice profiling naprieč jazykmi bez per-language trénovania. Priamo aplikovateľné pre Scriptorium cross-lingual retrieval.
- **Linky:**
  - [arXiv 2502.15168](https://arxiv.org/abs/2502.15168)

-----

### 12.2 StAyaL: Multilingual Style Transfer

- **Autori:** Karishma Thakrar, Katrina Lawrence, Kyle Howard
- **Venue:** arXiv
- **Rok:** January 2025
- **Kľúčový nález:** Individuálny writing style sa dá zachytiť ako high-dimensional embedding z iba 100 riadkov textu a preniesť naprieč jazykmi pre štylistickú generáciu aj cross-lingual preklad. Trojfázový prístup (data augmentation, style-content separácia, embedding aggregation) dosahuje 74.9% presnosť v topic-agnostic style identifikácii.
- **Relevancia pre Virgil:** Potvrdzuje Panza finding (100 samples stačí) a rozširuje ho na multilingválny kontext. Style-content separácia je presne Virgil architektúra (Style Summary vs. Scriptorium).
- **Linky:**
  - [arXiv 2501.11639](https://arxiv.org/abs/2501.11639)

-----

### 12.3 Multilingual Text Style Transfer: Datasets & Models for Indian Languages

- **Autori:** Sourabrata Mukherjee, Atul Kr. Ojha, Akanksha Bansal, Deepak Alok, John P. McCrae, Ondrej Dusek
- **Venue:** arXiv (revised August 2024)
- **Rok:** 2024
- **Kľúčový nález:** Prvý komplexný sentiment style transfer benchmark naprieč 8 indickými jazykmi (Hindi, Magahi, Malayalam, Marathi, Punjabi, Odia, Telugu, Urdu) s 1 000 paralelných viet per jazyk. Cross-lingual transfer z resource-rich jazykov výrazne zlepšuje výkon na low-resource jazykoch.
- **Relevancia pre Virgil:** Dôkaz že cross-lingual transfer funguje pre style tasks. Ak Virgil expanduje na non-English trhy, style knowledge z angličtiny sa dá čiastočne preniesť.
- **Linky:**
  - [arXiv 2405.20805](https://arxiv.org/abs/2405.20805)

-----

### 12.4 Evaluation of Multilingual LLMs Personalized Text Generation Capabilities Targeting Groups and Social-Media Platforms

- **Autori:** Dominik Macko
- **Venue:** arXiv
- **Rok:** January 2026
- **Kľúčový nález:** Evaluácia personalizovanej generácie naprieč 10 jazykmi pomocou 16 LLM (Llama 3.x, Gemma 2/3, Qwen 3) cez 1 080 prompt kombinácií (17 280 textov celkovo). Kvalita personalizácie a style preservation sa výrazne líšia medzi jazykmi — najvyššia efektivita v angličtine, degradácia v lower-resource jazykoch.
- **Relevancia pre Virgil:** Kvantifikuje "multilingual gap" — ak Virgil expanduje mimo angličtinu, musí počítať s nižšou kvalitou personalizácie a potenciálne agresívnejšou style grounding stratégiou pre non-English jazyky.
- **Linky:**
  - [arXiv 2601.03752](https://arxiv.org/abs/2601.03752)

-----

## 13. Long-Form Text Coherence & Structural Planning

### 13.1 CogWriter: A Cognitive Writing Perspective for Constrained Long-Form Text Generation

- **Autori:** Kaiyang Wan, Honglin Mu, Rui Hao, Haoran Luo, Tianle Gu, Xiuying Chen
- **Venue:** Findings of ACL 2025
- **Rok:** 2025
- **Kľúčový nález:** Training-free multi-agent framework inšpirovaný Cognitive Writing Theory — dekomponuje long-form generáciu na planning, translating, reviewing a monitoring fázy. S Qwen-2.5-14B ako backbone prekonáva GPT-4o o 22% na complex constrained long-form generácii.
- **Relevancia pre Virgil:** 🔑 Priamy architektonický vzor pre Virgil session flow. Multi-agent decomposition (plan → write → review → monitor) mapuje na Virgil session fázy. Potvrdzuje že aj menšie modely s proper orchestráciou prekonávajú veľké monolitické modely.
- **Linky:**
  - [arXiv 2502.12568](https://arxiv.org/abs/2502.12568)
  - [ACL Anthology](https://aclanthology.org/2025.findings-acl.511/)

-----

### 13.2 LongEval: A Comprehensive Analysis of Long-Text Generation Through a Plan-based Paradigm

- **Autori:** Siwei Wu, Yizhi Li, Xingwei Qu, Rishi Ravikumar, Yucheng Li, Tyler Loakman et al.
- **Venue:** arXiv (under review)
- **Rok:** February 2025
- **Kľúčový nález:** Evaluuje LLMs na long-text generácii cez priame aj plan-based paradigmy. Aktuálne LLMs zlyávajú na length requirements a information density — výkon sa deterioruje s rastúcou dĺžkou textu. Plan-based generácia (section-by-section s content plans) signifikantne zlepšuje koherenciu.
- **Relevancia pre Virgil:** Empiricky validuje Virgil outline-first prístup. Section-by-section generácia s content plans je presne čo Virgil robí v session flow (outline → expand sections → refine). Degradácia výkonu s dĺžkou textu vysvetľuje prečo je chunk-based editing lepší než whole-article generation.
- **Linky:**
  - [arXiv 2502.19103](https://arxiv.org/abs/2502.19103)

-----

### 13.3 LongGenBench: Long-context Generation Benchmark

- **Autori:** Xiang Liu, Peijie Dong, Xuming Hu, Xiaowen Chu
- **Venue:** Findings of EMNLP 2024
- **Rok:** 2024
- **Kľúčový nález:** Syntetický benchmark vyžadujúci od LLMs kohézne long-context odpovede. API aj open-source modely vykazujú performance degradation (1.2% až 47.1%) v long-context generácii — koherencia a instruction adherence klesajú s rastúcou output dĺžkou.
- **Relevancia pre Virgil:** Kvantifikuje koherenčný problém — blog posty (1 000–3 000 slov) spadajú do pásma kde LLMs začínajú strácať koherenciu. Potvrdzuje potrebu Virgil chunked generation approach.
- **Linky:**
  - [ACL Anthology](https://aclanthology.org/2024.findings-emnlp.48/)
  - [arXiv 2410.04199](https://arxiv.org/abs/2410.04199)

-----

### 13.4 StoryWriter: A Multi-Agent Framework for Long Story Generation

- **Autori:** Haotian Xia, Hao Peng, Yunjia Qi, Xiaozhi Wang, Bin Xu, Lei Hou, Juanzi Li (Tsinghua University)
- **Venue:** CIKM 2025
- **Rok:** 2025
- **Kľúčový nález:** Tri-modulárny multi-agent framework (outline agent, planning agent, writing agent s dynamic history compression) pre dlhé naratívy. Dataset ~6 000 príbehov priemerne 8 000 slov. Fine-tuned Llama3.1-8B a GLM4-9B prekonávajú baselines v kvalite aj dĺžke.
- **Relevancia pre Virgil:** Dynamic history compression je priamo relevantná pre Virgil session context management — pri dlhých článkoch musí systém komprimovať predchádzajúce sekcie aby si udržal konzistenciu bez context overflow.
- **Linky:**
  - [ACM Digital Library](https://dl.acm.org/doi/10.1145/3746252.3761616)
  - [arXiv 2506.16445](https://arxiv.org/abs/2506.16445)

-----

### 13.5 Shifting Long-Context LLMs Research from Input to Output

- **Autori:** viacero autorov
- **Venue:** arXiv
- **Rok:** March 2025
- **Kľúčový nález:** Argumentuje že výskum sa príliš zameriava na long-context input processing a zanedbáva long-context output generation. Syntetické tréningové dáta zavádzajú umelé závislosti, ktoré nezachytávajú real-world koherenčné vzorce. Extended context windows samotné neriešia koherenčnú degradáciu vo výstupoch presahujúcich ~2 000 slov.
- **Relevancia pre Virgil:** Pozičný paper potvrdzujúci že Virgil rieši skutočný problém. ~2 000 slov je breakpoint kde koherencia degraduje — väčšina blog postov je v tomto rozmedzí. Virgil chunked approach je architektonicky správna odpoveď.
- **Linky:**
  - [arXiv 2503.04723](https://arxiv.org/abs/2503.04723)

-----

## 14. Style Drift & Temporal Personalization

### 14.1 Right Now, Wrong Then: Non-Stationary Direct Preference Optimization under Preference Drift (NS-DPO)

- **Autori:** Seongho Son, William Bankes, Sayak Ray Chowdhury, Brooks Paige, Ilija Bogunovic
- **Venue:** ICML 2025
- **Rok:** 2025
- **Kľúčový nález:** Pridáva exponenciálny temporal weighting parameter do DPO loss funkcie, zameriavajúc učenie na novšie preference data. Teoretické konvergenčné garancie pod neznámym preference drift. Fine-tuned LLMs zostávajú robustné pod non-stationaritou, signifikantne prekonávajú baselines ignorujúce temporálne zmeny preferencií.
- **Relevancia pre Virgil:** 🔑 Teoretický základ pre style drift handling. Exponenciálne váženie novších exemplárov vs. starších — Virgil style summary by mal preferovať novšie články pri profile updates. Priamo aplikovateľné pre Phase 3 per-user fine-tuning.
- **Linky:**
  - [arXiv 2407.18676](https://arxiv.org/abs/2407.18676)

-----

### 14.2 SPRInG: Continual LLM Personalization via Selective Parametric Adaptation and Retrieval-Interpolated Generation

- **Autori:** Seoyeon Kim, Jaehyung Kim
- **Venue:** arXiv
- **Rok:** January 2026
- **Kľúčový nález:** Priamo adresuje preference drift v kontinuálnych user interaction streamoch. Implementuje drift-driven selective adaptation — izoluje high-novelty interakcie pre update user-specific adapterov, rozlišujúc genuínnu evolúciu preferencií od transient noise. Gated retrieval-interpolated generation dynamicky balancuje parametric knowledge s historickou evidenciou na logit level.
- **Relevancia pre Virgil:** 🔑 Najrelevantnejší paper pre Virgil temporal challenge. Kľúčový insight: rozlišovať medzi evolúciou štýlu (nový smer) vs. noise (jednorazová odchýlka). Virgil musí vedieť kedy updatnúť Style Summary vs. kedy ignorovať anomáliu.
- **Linky:**
  - [arXiv 2601.09974](https://arxiv.org/abs/2601.09974)

-----

### 14.3 Teaching Language Models to Evolve with Users: Dynamic Profile Modeling for Personalized Alignment (RLPA)

- **Autori:** Weixiang Zhao, Xingyu Sui, Yulin Hu, Jiahe Guo, Haixiao Liu, Biye Li, Yanyan Zhao, Bing Qin, Ting Liu
- **Venue:** NeurIPS 2025
- **Rok:** 2025
- **Kľúčový nález:** RL framework kde LLMs interagujú so simulovanými user modelmi a iteratívne inferujú a zlepšujú evolvujúce user profiles cez dialóg. Dual-level reward (profile accuracy + response consistency) prekonáva statický prompting, offline fine-tuning aj komerčné modely ako Claude-3.5 a GPT-4o.
- **Relevancia pre Virgil:** Architektonicky zaujímavé pre budúci Virgil — model ktorý aktívne detekuje zmeny v user profile cez interakciu. Dual-level reward štruktúra inšpiruje Virgil internal evaluation: profile accuracy (zodpovedá štýlu?) + response consistency (koherentný výstup?).
- **Linky:**
  - [arXiv 2505.15456](https://arxiv.org/abs/2505.15456)

-----

### 14.4 Beyond Dialogue Time: Temporal Semantic Memory for Personalized LLM Agents (TSM)

- **Autori:** viacero autorov
- **Venue:** arXiv
- **Rok:** January 2026
- **Kľúčový nález:** Identifikuje dva zlyhania v existujúcich LLM memory systémoch: temporal inaccuracy (organizovanie podľa dialogue time namiesto actual occurrence time) a temporal fragmentation (strata durative informácie o persistent states a evolving patterns). Navrhuje Temporal Semantic Memory modelujúci semantic time pre point-wise memory a podporujúci durative memory pre zachytenie user evolúcie.
- **Relevancia pre Virgil:** 🔑 Priamo adresuje ako ukladať evolúciu writingu v čase. Distinction medzi point-wise events (jednorazový experiment so štýlom) a durative states (postupná zmena tónu) je presne čo Virgil potrebuje pre temporal style profiling. Scriptorium by mal rozlišovať medzi jednorazovými a evolučnými vzorcami.
- **Linky:**
  - [arXiv 2601.07468](https://arxiv.org/abs/2601.07468)

-----

### 14.5 PRIME: LLM Personalization with Cognitive Dual-Memory

- **Autori:** viacero autorov
- **Venue:** arXiv
- **Rok:** July 2025
- **Kľúčový nález:** Mapuje episodic memory na interaction history a semantic memory na evolving user beliefs. Dual-memory architektúra lepšie zachytáva dlhodobé preferencie vs. krátkodobé kontextuálne signály.
- **Relevancia pre Virgil:** Episodic/semantic split mapuje na Virgil Scriptorium (episodic — konkrétne články) vs. Style Summary (semantic — abstrahované vzorce). Potvrdzuje architektonické rozhodnutie.
- **Linky:**
  - [arXiv 2507.04607](https://arxiv.org/abs/2507.04607)

-----

### 14.6 PersonaMem / Know Me, Respond to Me: Benchmark for Evolving User Profiles

- **Autori:** viacero autorov
- **Venue:** arXiv
- **Rok:** 2025
- **Kľúčový nález:** Benchmark ukazujúci že frontier modely dosahujú iba ~50% presnosť v sledovaní evolving user profiles naprieč sessions.
- **Relevancia pre Virgil:** Kvantifikuje gap — ak najlepšie modely zlyhávajú na 50%, Virgil nemôže spoliehať na implicit tracking. Explicit style summary updates sú nutnosť, nie luxus.
- **Linky:**
  - [arXiv 2504.14225](https://arxiv.org/abs/2504.14225)

-----

## Prioritizácia pre Virgil (Quick Reference)

|Priorita|Paper                          |Fáza   |Akcia                                               |
|--------|-------------------------------|-------|----------------------------------------------------|
|🔴 HIGH  |PPA (Post Persona Alignment)   |MVP    |Implementovať reverse pipeline pre selective editing|
|🔴 HIGH  |FineEdit / Diff-BLEU           |MVP    |Evaluation framework pre block edits                |
|🔴 HIGH  |Conversation Progress Guide    |MVP    |Progress UI pre interview wizard (dropout fix)      |
|🔴 HIGH  |CogWriter (multi-agent writing)|MVP    |Validate session flow against cognitive writing theory|
|🔴 HIGH  |LongEval (plan-based paradigm) |MVP    |Plan-based section generation as default approach   |
|🟠 MED   |CPER (From Guessing to Asking) |MVP    |Proaktívne elicitovanie v session flow              |
|🟠 MED   |CHAMELEON (Fake it then Align) |1.5    |Cold start riešenie — 1-shot synthetic bootstrap    |
|🟠 MED   |KG + RAG (WWW 2025)            |1.5    |Scriptorium ako Knowledge Graph                     |
|🟠 MED   |SPRInG (drift detection)       |1.5    |Style evolution vs. noise discrimination            |
|🟠 MED   |NS-DPO (temporal weighting)    |1.5    |Exponential recency weighting for style profiles    |
|🟠 MED   |TSM (temporal semantic memory) |1.5    |Point-wise vs. durative style changes in Scriptorium|
|🟠 MED   |mStyleDistance (multilingual)   |2.0    |Language-agnostic style embeddings for expansion    |
|🟡 LOW   |Contrastive Activation Steering|Phase 3|Style vectors namiesto prompt text                  |
|🟡 LOW   |OPPU (One PEFT Per User)       |Phase 3|Per-user LoRA fine-tuning                           |
|🟡 LOW   |StoryWriter (history compress) |Phase 3|Dynamic context compression for long articles       |

-----

*Dokument generovaný pre interné účely projektu Virgil. Posledná aktualizácia: Marec 2026.*
