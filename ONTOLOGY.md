# Heimdall Ontology

**Version:** 0.4.0
**Status:** Active initial vocabulary
**Last updated:** 2026-07-30

This document is the canonical source for every controlled vocabulary value in Heimdall. Dropdowns, keyboard shortcuts, API validation, imports, and exports must use these values exactly. Do not maintain a second hand-authored list in application code.

The ontology is deliberately small. Add a value only after observed use demonstrates a persistent gap. `Other` is permitted only where shown below and must be accompanied by commentary; review its use before adding a new controlled value.

## Annotation Fields

| Field | Required | Cardinality | Rule |
| --- | --- | --- | --- |
| Case | Yes | One | A saved document authority |
| Paragraphs | Yes | One or more | Exact saved paragraphs from the selected case |
| Research Track | Yes | One | Select from **Research Track** before adding legal detail |
| Bail Proceeding | Conditional | One | Required when Research Track is `Bail`; records case context |
| Bail Issue | Conditional | One | Required when Research Track is `Bail`; identifies the highlighted proposition's point of law |
| Bail Result | Conditional | One | Required when Research Track is `Bail`; records case context |
| Bail Factors | Conditional | Zero or more | Optional retrieval tags for legally salient facts or grounds in the highlighted passage |
| Type | Yes | One | Select from **Type** |
| Area | Yes | One or more | Select from **Area** |
| Authority Weight | Yes | One | Select from **Authority Weight** |
| Function | Yes | One | Select from **Function** |
| Relationship | No | Zero or one | Select from **Relationship**; link a related authority |
| Boundary | No | Zero or one | Select from **Boundary** |
| Trigger | No | Zero or more | Select from **Trigger** |
| Commentary | No* | One | Free text; required when any selected value is `Other` |
| Related Authorities | No | Zero or more | Saved document authorities |

`Case`, `Paragraphs`, and `Related Authorities` are provenance links, not controlled-value fields.

## Research Track

Research Track is the fast first classification. It determines which compact, purpose-built annotation form is shown. It classifies the legal proposition's home in the knowledge base, not the case as a whole. The general legal-context fields remain available as optional additional context.

| Value | Meaning |
| --- | --- |
| Merits | Trial, liability, or conviction decision, including an appeal from one |
| Sentencing | Sentence, sentencing appeal, or related disposition |
| Bail | Judicial interim release, review, or bail pending appeal |
| Charter and Procedure | Charter applications, evidence, procedure, and other pre-trial process |
| Other | Mixed or uncommon decision that does not fit a current track |

## Bail Proceeding

| Value | Meaning |
| --- | --- |
| Initial release (ss. 515/516) | Initial judicial interim release decision |
| Section 525 review | Delay review under s. 525 |
| Section 520/521 review | Review of a release or detention order |
| Appeal | Appeal concerning a bail decision |
| Bail pending appeal | Release pending appeal |
| Other | Another bail proceeding |

## Bail Issue

| Value | Meaning |
| --- | --- |
| Onus | Burden or reverse-onus question |
| Detention ground | Primary, secondary, or tertiary ground |
| Release form or surety | Form of release, surety, or supervision |
| Condition | A proposed, challenged, or varied condition |
| Delay | Delay affecting release or review |
| Evidence or procedure | Evidentiary or procedural issue in the bail process |
| Reasons | Sufficiency or adequacy of reasons |
| Other | Another principal bail issue |

## Bail Result

| Value | Meaning |
| --- | --- |
| Released | Release ordered or maintained |
| Detained | Detention ordered or maintained |
| Release varied | Release order or conditions varied |
| Review granted | Review allowed |
| Review dismissed | Review dismissed |
| Appeal granted | Appeal allowed |
| Appeal dismissed | Appeal dismissed |
| New hearing ordered | Matter remitted or ordered to a new hearing |
| Procedural disposition | Determined without a substantive release/detention outcome |
| Other | Another result not represented above |

## Bail Factors

Use these optional tags only for a legally salient factor actually addressed by the selected passage. They are retrieval aids, not a substitute for the proposition or for careful reading of the decision.

| Value | Meaning |
| --- | --- |
| Ground — Primary | The primary ground is in issue or addressed |
| Ground — Secondary | The secondary ground is in issue or addressed |
| Ground — Tertiary | The tertiary ground is in issue or addressed |
| Indigenous accused / Gladue | Indigenous background, Gladue principles, or related systemic factors are addressed |
| Intimate partner violence | Intimate partner violence or related complainant-safety context is addressed |
| Prior non-compliance | Prior breaches, failures to attend, or non-compliance with release terms are addressed |
| Surety or release plan | A surety, supervision, deposit, or proposed release plan is addressed |
| Delay | Delay is material to the release, review, or result |
| Substance use | Alcohol or drug use is materially addressed |
| Mental health | Mental health is materially addressed |
| Caregiving responsibilities | Children, dependants, or caregiving responsibilities are materially addressed |
| Other | Another recurring bail factor not represented above |

## Type

| Value | Meaning |
| --- | --- |
| Ratio | A proposition necessary to the decision's legal holding |
| Legal Test | A stated test, analytical framework, or required factors |
| Principle | A general legal principle applied or stated by the court |
| Key Quote | Especially useful wording that merits retrieval in its own right |
| Obiter | A non-binding observation or commentary from the court |
| Practice Point | A practical implication for litigation or advocacy |
| Procedural Point | A point about process, evidentiary steps, or procedural posture |
| Other | A provisional type not yet represented above |

## Area

Phase 1 begins with bail. Use the smallest value that accurately describes the proposition; apply multiple values only when a proposition genuinely spans them.

| Value | Meaning |
| --- | --- |
| Bail | Bail and judicial interim release generally |
| Bail — Grounds for Detention | Primary, secondary, and tertiary grounds |
| Bail — Release Conditions | Conditions, sureties, supervision, and least onerous release |
| Bail — Review and Variation | Review, variation, and related remedies |
| Bail — Charter | Charter issues arising in bail matters |
| Criminal Procedure | General criminal procedure outside the current bail focus |
| Charter | General Canadian Charter criminal-law issues |
| Sentencing | Sentencing principles and dispositions |
| Other | A provisional area not yet represented above |

## Authority Weight

Authority weight records the user's practical assessment of an authority's usefulness and force in the knowledge base. It does not itself determine whether a proposition is binding.

| Value | Meaning |
| --- | --- |
| Foundational | A leading or indispensable authority for the area |
| Significant | Material authority likely to guide analysis or submissions |
| Routine | Useful application or ordinary authority |
| Historical | Retained chiefly for history, context, or a superseded approach |

## Function

Function records how the proposition is expected to be used in legal reasoning or work product.

| Value | Meaning |
| --- | --- |
| States Rule | States the applicable rule or governing proposition |
| Explains Test | Explains a test, factors, or analytical sequence |
| Applies Test | Applies an existing test to facts |
| Defines Threshold | Identifies the threshold, burden, or standard |
| Supports Argument | Useful affirmative authority for an argument |
| Limits Argument | Identifies a constraint, exception, or adverse point |
| Distinguishes Facts | Identifies facts material to a distinction |
| Provides Remedy | Addresses result, order, or remedy |
| Practice Guidance | Provides a tactical or procedural lesson |
| Other | A provisional function not yet represented above |

## Relationship

Use a relationship only when the annotation links the selected case to a related authority. The relationship is expressed from the selected case toward the related authority.

| Value | Meaning |
| --- | --- |
| Affirms | Treats the related authority as affirmed or confirms its approach |
| Applies | Applies the related authority's rule or test |
| Distinguishes | Distinguishes the related authority |
| Limits | Narrows the scope or use of the related authority |
| Clarifies | Explains or resolves uncertainty in the related authority |
| Overrules | Overrules the related authority |
| Follows | Follows the related authority without a more specific relationship |
| Questions | Expresses doubt about the related authority |
| Other | A provisional relationship not yet represented above |

## Boundary

Boundary captures the limit of a proposition's proper use.

| Value | Meaning |
| --- | --- |
| Fact-Specific | Depends materially on the facts of the case |
| Procedural Posture | Depends on the procedural context |
| Statutory Context | Depends on particular statutory language or scheme |
| Jurisdiction-Specific | Applies only in a stated jurisdiction or court context |
| Temporal | Depends on a date, transition, or change in law |
| Superseded | Has been displaced, overruled, or made obsolete |
| None Identified | No particular boundary identified |
| Other | A provisional boundary not yet represented above |

## Trigger

Trigger captures a factual or procedural feature that should prompt retrieval of the proposition. Multiple values are allowed.

| Value | Meaning |
| --- | --- |
| Reverse Onus | A reverse-onus issue is present |
| Secondary Ground | Secondary-ground detention is in issue |
| Tertiary Ground | Tertiary-ground detention is in issue |
| Surety | A surety is proposed, required, or challenged |
| Release Condition | A release condition is proposed, challenged, or reviewed |
| Delay | Delay is material to the issue |
| Charter Breach | A Charter breach is alleged or established |
| Changed Circumstances | A material change supports review or variation |
| Publication Ban | A publication-ban issue is present |
| Other | A provisional trigger not yet represented above |

## Change Protocol

1. Record provisional gaps with `Other` and concise commentary.
2. Review accumulated `Other` use periodically; do not expand the ontology for a one-off use.
3. When adding, renaming, or retiring a value, increment this document's semantic version.
4. Document the migration mapping for any changed value.
5. Preserve the ontology version on every annotation so historic records remain interpretable.

## Version Notes

- **0.3.0:** `Decision Track` renamed to `Research Track` to make the proposition—not the case—the unit of classification. Added appeal/review result values for Bail.
- **0.4.0:** Added proposition-level `Bail Factors`. Replaced combined Bail result labels with explicit release, review, and appeal outcomes. Existing annotations retain their stored ontology version and historic result values.
