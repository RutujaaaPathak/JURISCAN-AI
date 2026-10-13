#!/usr/bin/env python3
"""Build and validate the JurisScan-AI pilot batch (JSIN_000001 - JSIN_000100)."""
import json, csv, re, sys, itertools
from collections import Counter

CAT = dict(
    T="TERMINATION", PF="PAYMENT_AND_FEES", LI="LIABILITY", IN="INDEMNIFICATION",
    CO="CONFIDENTIALITY", DP="DATA_PRIVACY", IP="INTELLECTUAL_PROPERTY",
    DR="DISPUTE_RESOLUTION", AR="ARBITRATION", JU="JURISDICTION_AND_GOVERNING_LAW",
    RE="RENEWAL_AND_AUTO_RENEWAL", NP="NOTICE_PERIOD",
    PL="PENALTIES_AND_LIQUIDATED_DAMAGES", WR="WARRANTIES_AND_REPRESENTATIONS",
    SL="SERVICE_LEVELS_AND_DELIVERABLES", NC="NON_COMPETE_AND_NON_SOLICITATION",
    FM="FORCE_MAJEURE", PD="PAYMENT_DEFAULT_AND_LATE_FEES",
    AS="ASSIGNMENT_AND_SUBCONTRACTING", AU="AUDIT_AND_ACCESS_RIGHTS",
    EC="EMPLOYMENT_AND_COMPENSATION", RT="RENTAL_AND_TENANCY",
    CR="CONSUMER_RIGHTS_AND_REFUNDS", CN="CONSENT_AND_AUTHORIZATION", OT="OTHER")
PARTY = dict(TEN="TENANT", LAN="LANDLORD", EMP="EMPLOYEE", EMR="EMPLOYER",
    SP="SERVICE_PROVIDER", SR="SERVICE_RECIPIENT", CON="CONSUMER", DPR="DATA_PRINCIPAL",
    DIS="DISCLOSING_PARTY", REC="RECEIVING_PARTY", FRL="FREELANCER", CLI="CLIENT",
    VEN="VENDOR", BUY="BUYER", BOTH="BOTH_PARTIES")
CT = dict(RL="RENTAL_LEASE", EM="EMPLOYMENT", SA="SERVICE_AGREEMENT", NDA="NDA",
    PP="PRIVACY_POLICY", TC="TERMS_AND_CONDITIONS", FC="FREELANCE_CONSULTING",
    VB="VENDOR_BUSINESS", CS="CONSUMER_SERVICE")
RT_ = dict(LEG="LEGAL_COMPLIANCE", FIN="FINANCIAL", PRI="PRIVACY", CTR="CONTRACTUAL",
    OPS="OPERATIONAL", NONE="NONE")

CAND = "Candidate provision for expert verification (not verified): "
N_S74 = CAND + "Indian Contract Act, 1872, s.74 (compensation where a sum is named as penalty/liquidated damages)."
N_S27 = CAND + "Indian Contract Act, 1872, s.27 (agreements in restraint of trade); in-term and post-termination restraints are treated differently, so verify current case law."
N_S28 = CAND + "Indian Contract Act, 1872, s.28 (agreements restraining legal proceedings or limiting time to enforce rights)."
N_S73 = CAND + "Indian Contract Act, 1872, ss.73-74 (damages for breach; forfeiture/penalty)."
N_S56 = CAND + "Indian Contract Act, 1872, s.56 (impossibility/frustration)."
N_DPDP = CAND + "Digital Personal Data Protection Act, 2023 and its rules (commencement and phase-in status must be verified before relying on it); IT Act 2000 s.43A and the SPDI Rules 2011 may also apply to sensitive data."
N_CPA = CAND + "Consumer Protection Act, 2019 (unfair contract / unfair trade practice provisions; specific sections to be verified)."
N_ARB = CAND + "Arbitration and Conciliation Act, 1996 (appointment and arbitrator-ineligibility provisions, incl. s.12(5) and the Seventh Schedule)."
N_ARB7 = CAND + "Arbitration and Conciliation Act, 1996 (arbitration agreement and seat provisions; sections to be verified)."
N_RENT = "Tenancy rules vary by State; verify against the law of the State where the premises are located."
N_WAGE = CAND + "applicable wage legislation on deductions and withholding (Payment of Wages Act, 1936 or the corresponding Labour Code); applicability depends on employee category and State."
N_COPY = CAND + "Copyright Act, 1957 (ownership and assignment provisions for works made in employment or under assignment)."
N_SOG = CAND + "Sale of Goods Act, 1930 (implied conditions and warranties)."
N_TPA = CAND + "Transfer of Property Act, 1882 (lessor and lessee rights and duties)."

# (cat, risk, text, reason, party, risktype, ctype, ctx, ref, notes, group)
def R(cat, risk, text, reason, party, rtype, ctype, ctx=False, ref="NA", notes=None, grp=None):
    return (cat, risk, text, reason, party, rtype, ctype, ctx, ref, notes, grp)

ROWS = [
# ---- TERMINATION
R("T","LOW","Either party may terminate this Agreement by giving the other party sixty (60) days' prior written notice. The Employer may also terminate the Employee's employment without notice for gross misconduct, provided the Employee has been given a written statement of the allegations and a reasonable opportunity to respond.","Termination right is mutual with reasonable notice, and summary dismissal is tied to a defined ground with a hearing opportunity.","EMP","NONE","EM"),
R("T","MEDIUM","The Company may terminate this Agreement at any time for convenience by giving the Service Provider written notice. Upon termination, the Company shall pay for services performed up to the date of termination.","Only the Company has a convenience termination right and no minimum notice is stated; payment for work done limits the financial exposure.","SP","CTR","SA"),
R("T","HIGH","The Client may terminate this Agreement immediately and without notice at its sole discretion, and in such event the Freelancer shall forfeit all unpaid fees for work already completed and shall return all advance payments received.","Unilateral immediate termination combined with forfeiture of fees for completed work and refund of advances exposes the Freelancer to severe loss with no procedural protection.","FRL","FIN","FC",False,"NR",N_S73),
R("T","LOW","The Tenant may terminate this tenancy at any time after the lock-in period of six (6) months by giving the Landlord one (1) month's written notice. The Landlord may terminate only for non-payment of rent for two consecutive months, a material breach left uncured thirty (30) days after written notice, or as permitted by applicable law.","Both sides have defined exit routes; the Landlord's grounds are limited and subject to notice and cure.","TEN","NONE","RL",True,"NR","Context needed: State-specific tenancy law may add or restrict grounds. "+N_RENT),
R("T","MEDIUM","We may suspend or terminate your account if we reasonably believe you have violated these Terms. We will try to notify you before termination where practicable, but are not obliged to do so.","A reasonableness standard limits the discretion, but prior notice is not guaranteed and no appeal or cure process is described.","CON","OPS","TC"),
# ---- PAYMENT_AND_FEES
R("PF","LOW","The Client shall pay the Service Provider a fixed monthly fee of INR 85,000 plus applicable GST, payable within fifteen (15) days of receipt of a valid tax invoice. Invoices shall be raised on the last working day of each month.","Amount, tax treatment, due date and invoice trigger are all stated clearly.","BOTH","NONE","SA"),
R("PF","MEDIUM","The Company may revise its subscription fees from time to time. Revised fees will apply from the next billing cycle after the revision is published on the website.","Unilateral fee change with notice only by website publication; no cap or right to exit before the new fee applies.","CON","FIN","TC"),
R("PF","HIGH","In addition to the subscription fee, the User shall pay such processing, platform and administrative charges as the Company may determine, which shall be debited from the User's registered payment instrument without prior intimation.","Undefined, company-determined charges debited without notice give the User no ability to anticipate or contest charges.","CON","FIN","CS",False,"NR",N_CPA),
R("PF","MEDIUM","The Freelancer shall be paid INR 40,000 upon final acceptance of the deliverables. The Client shall have thirty (30) days from delivery to accept or reject the deliverables.","Entire fee is deferred to an acceptance step with no stated acceptance criteria or deemed-acceptance rule.","FRL","FIN","FC"),
R("PF","LOW","All amounts payable under this Agreement are exclusive of GST. The Buyer shall deduct tax at source where required under applicable law and shall furnish the corresponding certificate to the Vendor within the period prescribed by law.","Tax treatment is clear and defers to applicable law; no concerning discretion.","BOTH","NONE","VB"),
# ---- LIABILITY
R("LI","LOW","Neither party shall be liable to the other for indirect or consequential loss. Each party's aggregate liability under this Agreement shall not exceed the total fees paid or payable in the twelve (12) months preceding the claim, except for liability arising from fraud, wilful misconduct, death or personal injury, or breach of confidentiality.","Mutual cap tied to fees with standard carve-outs for serious misconduct.","BOTH","NONE","VB",True,"NA","Adequacy of the cap depends on contract value, insurance and related indemnities that are not in this excerpt.","liability_cap"),
R("LI","MEDIUM","The Service Provider's total liability under this Agreement shall in no event exceed INR 1,00,000, regardless of the cause of action.","Fixed low cap with no carve-outs may leave the Service Recipient under-protected, but whether it is inadequate depends on contract value.","SR","FIN","SA",True,"NA","Missing context: total contract value, data or safety exposure, and any carve-outs elsewhere.","liability_cap"),
R("LI","HIGH","The Client shall be liable for all losses, damages, costs and expenses of any nature whatsoever, whether direct or indirect, foreseeable or otherwise, arising out of or in connection with this Agreement, without any limit, while the Service Provider shall have no liability to the Client.","Uncapped, open-ended liability on one party including unforeseeable loss, with the counterparty fully excluded.","CLI","FIN","SA",False,"NR",N_S73),
R("LI","MEDIUM","The Platform is provided on an 'as is' basis. To the maximum extent permitted by law, the Company excludes all liability for any loss arising from the use of the Platform.","Broad exclusion of liability toward consumers; the 'to the extent permitted by law' qualifier mitigates but leaves scope unclear.","CON","LEG","TC",False,"NR",N_CPA),
R("LI","LOW","The Landlord shall not be liable for loss of or damage to the Tenant's personal belongings except where caused by the Landlord's negligence or by a failure to repair a defect notified in writing by the Tenant.","Reasonable allocation: exclusion applies except where the Landlord is at fault or ignores notified defects.","TEN","NONE","RL"),
# ---- INDEMNIFICATION
R("IN","LOW","Each party shall indemnify the other against third-party claims arising from its breach of applicable law in performing this Agreement, provided that the indemnified party promptly notifies the indemnifying party, permits it to control the defence, and mitigates its losses.","Mutual, fault-based, with notice, defence control and mitigation safeguards.","BOTH","NONE","VB"),
R("IN","MEDIUM","The Freelancer shall indemnify the Client against any third-party claim that the deliverables infringe intellectual property rights, except to the extent the infringement results from materials or instructions supplied by the Client.","Customary IP indemnity with a client-materials carve-out, but uncapped and with no procedure; weight depends on the fee.","FRL","FIN","FC",True,"NA","Missing context: fee size, any liability cap, and whether the Freelancer can control the defence."),
R("IN","HIGH","The Service Provider shall indemnify and hold harmless the Company, its affiliates, directors and employees from all claims, losses, penalties and expenses of any kind arising out of this Agreement, whether or not caused by the Service Provider, without limit as to amount.","Indemnity applies regardless of fault, covers affiliates and individuals, and is uncapped.","SP","FIN","SA"),
R("IN","MEDIUM","The Employee shall indemnify the Company for any loss caused to the Company by the Employee's negligence in the course of duties.","Employee exposure for ordinary negligence with no cap, process or proof standard; enforceability against employees may depend on law and facts.","EMP","FIN","EM",True,"NR","Missing context: any cap, deduction mechanism and employee category. "+N_WAGE),
R("IN","LOW","The User shall indemnify the Company against third-party claims arising from content uploaded by the User in violation of these Terms, provided the Company gives prompt written notice and the User's liability is limited to losses directly attributable to the violation.","Indemnity is limited to the User's own violation, with notice and a directness limit.","CON","NONE","TC"),
# ---- CONFIDENTIALITY
R("CO","LOW","Confidential Information excludes information that (a) is or becomes public other than through breach, (b) was lawfully known to the Receiving Party before disclosure, (c) is independently developed without use of the Disclosing Party's information, or (d) is required to be disclosed by law or court order, subject to prior written notice to the Disclosing Party where lawful.","Standard exclusions and a compelled-disclosure mechanism with notice.","BOTH","NONE","NDA"),
R("CO","MEDIUM","Confidential Information means all information disclosed by the Disclosing Party in any form, whether or not marked as confidential.","Very broad definition with no stated exclusions in this excerpt; may sweep in public or independently known information.","REC","CTR","NDA",True,"NA","Missing context: exclusions or a marking standard may appear in other clauses.","conf_scope"),
R("CO","HIGH","The Receiving Party's confidentiality obligations shall continue in perpetuity and shall apply to all information of any nature received from the Disclosing Party, including information that is publicly available, and the Receiving Party shall pay liquidated damages of INR 50,00,000 for each breach.","Perpetual duty covering public information, plus a large fixed sum per breach regardless of loss.","REC","FIN","NDA",False,"NR",N_S74,"conf_scope"),
R("CO","LOW","During employment and for two (2) years afterwards, the Employee shall not disclose the Company's trade secrets or non-public client data except as required in the course of duties or by law. This does not restrict the Employee's use of general skills, knowledge and experience.","Time-limited, scoped to trade secrets and client data, with an express carve-out for general skills.","EMP","NONE","EM"),
R("CO","MEDIUM","The Vendor may disclose the Buyer's Confidential Information to its affiliates, subcontractors and advisers on a need-to-know basis.","Onward disclosure is allowed but the clause does not require recipients to be bound by equivalent obligations.","BUY","CTR","VB"),
# ---- DATA_PRIVACY
R("DP","LOW","We process your personal data only for the purposes described in this Policy and for which you have given consent. You may withdraw your consent at any time by writing to our Grievance Officer at the address below, and we will stop processing your data for those purposes within a reasonable period, except where retention is required by law.","Purpose limitation, withdrawal route and a named grievance contact are provided.","DPR","NONE","PP",False,"NR",N_DPDP),
R("DP","MEDIUM","We may retain your personal data for as long as necessary for our business purposes.","No defined retention period or deletion trigger; 'business purposes' is open-ended.","DPR","PRI","PP",False,"NR",N_DPDP),
R("DP","HIGH","By using the Service you authorise the Company to share your personal data, including financial and health information, with any third party of its choice for any purpose, and you waive any right to object to such sharing.","Unrestricted sharing of sensitive data for any purpose with a blanket waiver and no safeguards.","DPR","PRI","PP",False,"NR",N_DPDP),
R("DP","LOW","The Service Provider shall process the Client's personal data only on the Client's documented instructions, implement reasonable security safeguards against unauthorised access, and notify the Client without undue delay on becoming aware of a personal data breach.","Instruction-bound processing, security duty and breach notification.","SR","NONE","SA",False,"NR",N_DPDP),
R("DP","MEDIUM","The Employee consents to the Company monitoring the use of Company devices and accounts and collecting such data as it considers necessary for security and performance management.","Monitoring scope is determined by the Company; purposes are stated but limits, retention and access are not.","EMP","PRI","EM",True,"NR","Missing context: monitoring policy, retention and whether personal use is permitted. "+N_DPDP),
# ---- INTELLECTUAL_PROPERTY
R("IP","LOW","Upon receipt of full payment, the Freelancer assigns to the Client in perpetuity and throughout the world all rights in the deliverables created specifically for the Client under this Agreement. The Freelancer retains ownership of pre-existing tools, templates and know-how and grants the Client a non-exclusive licence to use them as embedded in the deliverables.","Assignment is tied to payment, states duration and territory, and preserves the Freelancer's background IP.","BOTH","NONE","FC",False,"NR",N_COPY),
R("IP","HIGH","All inventions, works and ideas conceived by the Employee during the term of employment, whether or not related to the Company's business and whether or not made during working hours, shall belong exclusively to the Company.","Claims ownership of unrelated, off-hours work, which is a significant overreach into the Employee's own creations.","EMP","LEG","EM",True,"NR","Missing context: any carve-out schedule for prior or personal work. "+N_COPY),
R("IP","MEDIUM","The Client shall own all deliverables from the moment of creation. The Freelancer shall not use the deliverables in a portfolio without the Client's prior written consent.","Ownership passes before payment and portfolio use is barred; both favour the Client but are common negotiating points.","FRL","CTR","FC",True,"NA","Missing context: payment terms and whether ownership is conditional on payment."),
R("IP","MEDIUM","By uploading content to the Platform, you grant the Company a worldwide, royalty-free, sublicensable licence to use, modify and distribute that content for the purpose of operating and promoting the Platform.","Broad licence limited by purpose, but duration, revocation on deletion and sublicensee scope are unspecified.","CON","CTR","TC"),
R("IP","LOW","The Vendor retains all intellectual property rights in the Software. The Buyer is granted a non-exclusive, non-transferable licence to use the Software for its internal business purposes during the term of this Agreement. Customer data remains the exclusive property of the Buyer.","Clear licence scope and ownership split; customer data ownership is protected.","BOTH","NONE","VB"),
# ---- DISPUTE_RESOLUTION
R("DR","LOW","Any dispute shall first be referred to designated senior representatives of both parties, who shall meet within fifteen (15) days of a written dispute notice and attempt in good faith to resolve it. If unresolved within thirty (30) days, either party may pursue the remedies available under this Agreement.","Defined, time-bound, mutual escalation without barring later remedies.","BOTH","NONE","SA"),
R("DR","MEDIUM","Any complaint must be raised with the Company within seven (7) days of the event giving rise to it, failing which it shall be deemed waived.","Very short claim window that extinguishes the complaint; may be challenged but legal effect is uncertain.","CON","LEG","TC",True,"NR","Missing context: nature of claims covered and the governing limitation rules. "+N_S28),
R("DR","HIGH","Any dispute shall be resolved solely by the Managing Director of the Company, whose decision shall be final and binding on the Vendor.","A single officer of the counterparty is the sole, final decision-maker, leaving the Vendor without an independent forum.","VEN","LEG","VB",False,"NR",N_ARB),
# ---- ARBITRATION
R("AR","LOW","Any dispute arising out of this Agreement shall be finally resolved by arbitration under the Arbitration and Conciliation Act, 1996 before a sole arbitrator appointed by mutual consent of the parties. The seat and venue of arbitration shall be Mumbai and the language shall be English.","Mutual appointment, defined seat and language, statute named.","BOTH","NONE","SA",False,"NR",N_ARB7),
R("AR","HIGH","All disputes shall be referred to arbitration by a sole arbitrator appointed by the Company. The seat of arbitration shall be Bengaluru.","One party unilaterally appoints the sole arbitrator, raising independence and enforceability concerns.","CON","LEG","CS",False,"NR",N_ARB,"arb_appointment"),
R("AR","MEDIUM","Any dispute arising out of employment shall be resolved by arbitration in accordance with the Arbitration and Conciliation Act, 1996. The costs of arbitration shall be borne equally by the parties.","Equal cost sharing can burden an individual employee, and the appointment method is not stated.","EMP","FIN","EM",True,"NR","Missing context: appointment mechanism and fee schedule. "+N_ARB7),
R("AR","LOW","Disputes shall be referred to a tribunal of three arbitrators, with each party appointing one arbitrator and the two so appointed appointing the presiding arbitrator. The seat shall be New Delhi and the proceedings shall be conducted in English.","Balanced party-nominated tribunal with an agreed chair, seat and language.","BOTH","NONE","VB",False,"NR",N_ARB7,"arb_appointment"),
R("AR","MEDIUM","The parties agree to arbitrate all disputes. The decision of the arbitrator shall be final and no application may be made to any court in respect of the award.","Purports to exclude all court recourse; whether such exclusion is effective under the statute is uncertain.","BOTH","LEG","TC",False,"NR",N_ARB7),
# ---- JURISDICTION
R("JU","LOW","This Agreement shall be governed by the laws of India. Subject to the arbitration clause, the courts at New Delhi shall have exclusive jurisdiction over any matter arising from this Agreement.","Standard governing-law and forum clause that is mutual and clear.","BOTH","NONE","SA"),
R("JU","MEDIUM","These Terms are governed by Indian law. Any proceedings shall be brought exclusively before the courts at Pune, regardless of where the User resides.","Distant exclusive forum may burden consumers; whether it restricts consumer forums is a legal question.","CON","LEG","TC",True,"NR","Missing context: value of typical claims and consumer-forum rules on where complaints may be filed. "+N_CPA),
R("JU","HIGH","This Agreement shall be governed by the laws of the State of Delaware, USA, and the Employee irrevocably submits to the exclusive jurisdiction of the courts of Delaware for all disputes, notwithstanding that the Employee resides and works in India.","Foreign law and forum imposed on an India-based employee make enforcement of rights impractical.","EMP","LEG","EM",True,"NA","Missing context: parent-company structure and any Indian mandatory-law protections; label based on practical access to remedies."),
R("JU","LOW","This Agreement shall be governed by the laws of India and the rent control legislation applicable in the State where the Premises are located. Courts having territorial jurisdiction over the Premises shall have jurisdiction.","Forum follows the property; applicable tenancy law is respected.","BOTH","NONE","RL",True,"NR","Missing context: which State's law applies. "+N_RENT),
# ---- RENEWAL
R("RE","LOW","This Agreement shall renew for successive terms of twelve (12) months only if both parties agree in writing at least thirty (30) days before the expiry of the then-current term.","Renewal requires mutual written agreement; no automatic lock-in.","BOTH","NONE","SA"),
R("RE","MEDIUM","Your subscription will automatically renew for the same period unless you cancel at least seven (7) days before the renewal date through your account settings.","Auto-renewal is disclosed and cancellation is clear, but the cancellation window is short.","CON","FIN","TC",False,"NA",None,"auto_renewal"),
R("RE","HIGH","Subscriptions renew automatically each year at the then-current price. No notice of renewal or price change will be sent, and no refund will be given for any renewal charged.","Silent renewal at an unknown price with no notice and no refund.","CON","FIN","CS",False,"NR",N_CPA,"auto_renewal"),
R("RE","MEDIUM","The Landlord may, at its sole option, extend this Agreement for a further period of eleven (11) months on the same terms by notifying the Tenant, and the Tenant shall be bound by such extension.","Landlord-only extension option binds the Tenant, who loses the ability to leave at term end.","TEN","CTR","RL",True,"NR","Missing context: lock-in, rent-escalation and exit clauses. "+N_RENT),
# ---- NOTICE_PERIOD
R("NP","LOW","The Employee shall serve a notice period of sixty (60) days. The Company may waive the notice period in whole or in part, in which case it shall pay the Employee salary for the waived period.","Defined period, and the Company bears the cost if it waives notice.","EMP","NONE","EM"),
R("NP","MEDIUM","The Employee shall serve a notice period of ninety (90) days. The Company may terminate the Employee's employment by giving thirty (30) days' notice.","Notice obligations are asymmetric (90 days vs 30 days).","EMP","CTR","EM"),
R("NP","HIGH","Failing completion of the full 180-day notice period, the Employee shall forfeit all accrued salary, bonus and dues, and the Company may withhold the relieving letter and experience certificate until the period is completed.","Long notice with forfeiture of earned wages and withholding of career documents.","EMP","LEG","EM",False,"NR",N_WAGE),
R("NP","LOW","Notices under this Agreement shall be in writing and delivered by hand, registered post or email to the addresses stated in the Schedule, and shall be deemed received on delivery or, for email, on the next working day. Either party may change its address by written notice.","Clear, mutual service and deemed-receipt mechanics.","BOTH","NONE","RL"),
# ---- PENALTIES_LD
R("PL","LOW","If the Vendor fails to deliver the Goods by the agreed date, the Buyer may claim liquidated damages at 0.5% of the value of the delayed Goods per week of delay, subject to a maximum of 5% of the contract value. The parties agree that this is a genuine pre-estimate of loss.","Proportionate rate with a cap and a stated pre-estimate rationale.","VEN","NONE","VB",False,"NR",N_S74),
R("PL","MEDIUM","For each day of delay in completing the Services, the Service Provider shall pay the Client INR 25,000 as damages.","Fixed daily sum with no cap or link to loss; proportionality depends on contract value.","SP","FIN","SA",True,"NR","Missing context: contract value and any cap elsewhere. "+N_S74),
R("PL","HIGH","If the Employee leaves the Company within three (3) years of joining, the Employee shall pay the Company INR 10,00,000 as a penalty irrespective of the loss suffered by the Company.","Large fixed sum labelled a penalty and payable regardless of loss, long lock-in.","EMP","FIN","EM",True,"NR","Missing context: salary level and any training cost incurred by the Company. "+N_S74),
R("PL","MEDIUM","If the Tenant vacates the Premises before the end of the lock-in period, the Tenant shall pay the Landlord the rent for the entire remaining lock-in period, without reduction for any re-letting.","Common structure, but no credit for re-letting leaves the Tenant paying twice in some cases.","TEN","FIN","RL",False,"NR",N_S74),
# ---- WARRANTIES
R("WR","LOW","The Service Provider warrants that the Services will be performed with reasonable skill and care by suitably qualified personnel, and that it will re-perform any non-conforming Services at no additional charge if notified within thirty (30) days of delivery.","Reasonable standard with a defined remedy and notification window.","SR","NONE","SA"),
R("WR","MEDIUM","The Vendor makes no warranty, express or implied, regarding the Goods other than as expressly stated in this Agreement.","Disclaims implied terms; effect depends on what express warranties exist elsewhere and on mandatory implied terms.","BUY","LEG","VB",True,"NR","Missing context: express warranty clause. "+N_SOG),
R("WR","HIGH","The Freelancer represents and warrants that the deliverables will be free from any error, will achieve the business results desired by the Client, and will not infringe any rights worldwide, and the Freelancer shall bear all consequences of any failure of this warranty.","Absolute, results-based warranty with unlimited consequences for the Freelancer.","FRL","FIN","FC"),
# ---- SERVICE LEVELS
R("SL","LOW","The Service Provider shall maintain monthly uptime of at least 99.5%, measured excluding scheduled maintenance notified at least 48 hours in advance. If uptime falls below this level, the Client shall receive a service credit of 5% of the monthly fee for each full percentage point of shortfall, up to 25% of the monthly fee.","Measurable standard, defined exclusions and a stated remedy.","SR","NONE","SA"),
R("SL","MEDIUM","The Service Provider shall use reasonable efforts to resolve reported issues promptly.","No measurable response or resolution time and no remedy, so the commitment is hard to enforce.","SR","OPS","SA"),
R("SL","HIGH","Deliverables shall be deemed accepted only upon written sign-off by the Client, which may be withheld in the Client's absolute discretion, and payment for the deliverables shall be due only after such acceptance.","Acceptance and payment depend on unreviewable discretion, so the Provider can be left unpaid indefinitely.","SP","FIN","SA"),
# ---- NON_COMPETE
R("NC","LOW","During the term of employment, the Employee shall not engage in any business that competes with the Company's business, nor accept any other employment, without the Company's prior written consent.","Restraint is limited to the period of employment and is common and generally less problematic.","EMP","NONE","EM",True,"NR","Missing context: breadth of 'competes' and any carve-outs. "+N_S27),
R("NC","HIGH","For a period of three (3) years after termination, the Employee shall not, anywhere in India, work for or provide services to any entity engaged in a business similar to that of the Company.","Long, nationwide post-termination bar on working in the field, which is a serious enforceability and livelihood concern.","EMP","LEG","EM",False,"NR",N_S27,"post_employment_restraint"),
R("NC","MEDIUM","For twelve (12) months after termination, the Employee shall not directly solicit the Company's employees to leave their employment.","Narrower non-solicit of staff; enforceability uncertain but exposure is limited.","EMP","LEG","EM",True,"NR","Missing context: whether the clause also restricts hiring. "+N_S27,"post_employment_restraint"),
R("NC","MEDIUM","For six (6) months after termination, the Freelancer shall not provide services to any client introduced to the Freelancer by the Company.","Customer-specific, short restraint, but still limits the Freelancer's livelihood.","FRL","LEG","FC",False,"NR",N_S27),
# ---- FORCE_MAJEURE
R("FM","LOW","Neither party shall be liable for delay or failure in performance caused by events beyond its reasonable control, including natural disasters, war, epidemic or government action, provided that it notifies the other party within seven (7) days, uses reasonable efforts to mitigate, and resumes performance promptly. If the event continues for more than ninety (90) days, either party may terminate by written notice.","Mutual, defined events, notice and mitigation duties, and an exit right.","BOTH","NONE","VB",False,"NR",N_S56),
R("FM","MEDIUM","The Tenant shall not be entitled to any abatement of rent on account of any event of force majeure.","Tenant bears all risk even if the Premises become unusable.","TEN","FIN","RL",True,"NR","Missing context: whether the Premises are usable and whether other clauses allow rent relief. "+N_S56),
R("FM","HIGH","The Company may, at its discretion, declare any circumstance to be a force majeure event, in which case the Company shall be excused from all obligations to the User without any obligation to refund prepaid amounts.","Company defines the excusing event unilaterally and keeps prepaid money.","CON","FIN","CS",False,"NR",N_CPA),
# ---- PAYMENT_DEFAULT
R("PD","LOW","Interest at 1% per month shall accrue on undisputed invoices unpaid beyond the due date, calculated from the due date until the date of payment. The Vendor shall give ten (10) days' written notice before suspending performance for non-payment.","Moderate rate limited to undisputed sums, with notice before suspension.","BUY","NONE","VB"),
R("PD","MEDIUM","If rent is not paid by the 5th of the month, the Tenant shall pay a late fee of INR 500 per day until payment.","Fixed daily late fee with no cap or grace period; may be disproportionate over time.","TEN","FIN","RL"),
R("PD","HIGH","If any instalment is delayed, interest at 5% per month shall be charged on the entire outstanding amount, compounded monthly, and the Company may recall all dues and disable the User's access immediately.","Very high compounded rate on the whole balance with immediate acceleration and no cure period.","CON","FIN","CS",False,"NR",N_S74),
# ---- ASSIGNMENT
R("AS","LOW","Neither party may assign this Agreement without the prior written consent of the other, which shall not be unreasonably withheld. Either party may assign to a successor in a merger or sale of substantially all its business on written notice to the other.","Mutual consent with a reasonableness standard and a clear successor exception.","BOTH","NONE","SA"),
R("AS","MEDIUM","The Vendor may subcontract any part of the Services to third parties without the Buyer's consent, remaining responsible for the acts of its subcontractors.","Subcontracting without consent can affect quality and confidentiality, partly mitigated by continued Vendor responsibility.","BUY","OPS","VB"),
R("AS","HIGH","The Company may assign this Agreement and the Employee's employment to any person at its discretion, and the Employee agrees to work for the assignee on such terms as the assignee may notify.","Employee is moved to an unknown employer on terms set later by that employer.","EMP","CTR","EM",False,"NA"),
# ---- AUDIT
R("AU","LOW","The Buyer may, on fourteen (14) days' written notice and not more than once in any twelve-month period, audit the Vendor's relevant records during business hours, subject to confidentiality obligations. The Buyer shall bear the cost of the audit unless it reveals an overcharge exceeding 5%.","Limited frequency, notice, scope and cost allocation.","VEN","NONE","VB"),
R("AU","MEDIUM","The Client may access the Service Provider's premises and systems at any time to verify compliance with this Agreement.","No notice, frequency or scope limits; could disrupt operations and expose other clients' data.","SP","OPS","SA"),
R("AU","HIGH","The Company shall have an unrestricted right to access, inspect and copy all data stored on any personal device, account or storage medium used by the Employee, at any time and without notice.","Unbounded access to personal devices and accounts with no notice or limits.","EMP","PRI","EM",False,"NR",N_DPDP),
# ---- EMPLOYMENT_AND_COMPENSATION
R("EC","LOW","The Employee shall receive an annual cost-to-company of INR 12,00,000, comprising basic salary, house rent allowance and special allowance as set out in Annexure A, payable monthly by the last working day after statutory deductions.","Amount, components and payment timing are clear.","EMP","NONE","EM"),
R("EC","MEDIUM","Variable pay is discretionary and payable only if the Employee is in service on the payout date, and shall be determined by the Company based on business performance.","Company discretion and service condition make variable pay uncertain, though not necessarily unlawful.","EMP","FIN","EM"),
R("EC","HIGH","The Company may reduce the Employee's salary, allowances or benefits at any time at its sole discretion by giving written intimation, and continued service shall constitute acceptance.","Unilateral reduction of core pay with deemed consent by continued service.","EMP","FIN","EM",False,"NR",N_WAGE),
R("EC","LOW","The Employee shall be entitled to eighteen (18) days of paid leave per year. Up to ten (10) days of unavailed leave may be carried forward, and any balance shall be encashed at basic salary at year end.","Defined entitlement with carry-forward and encashment of the balance.","EMP","NONE","EM",True,"NA","Missing context: State shops-and-establishments or other law may prescribe minimum leave."),
# ---- RENTAL
R("RT","LOW","The Tenant shall pay a refundable security deposit of two (2) months' rent. The Landlord shall refund the deposit within thirty (30) days of the Tenant handing over vacant possession, after deducting only documented arrears of rent or the cost of repairing damage beyond normal wear and tear.","Moderate deposit, fixed refund timeline and limited, documented deductions.","TEN","NONE","RL",True,"NR","Missing context: State rules may cap deposits. "+N_RENT),
R("RT","MEDIUM","The monthly rent shall be increased by such amount as the Landlord may reasonably determine at the start of each year.","Escalation is unquantified and left to the Landlord, though a reasonableness standard applies.","TEN","FIN","RL",True,"NR","Missing context: any statutory limit on rent increases. "+N_RENT),
R("RT","HIGH","The Landlord may enter the Premises at any time, with or without notice, for any purpose, and may terminate the tenancy and re-let the Premises without notice if the Tenant refuses entry.","Unrestricted entry with eviction for refusal undermines peaceful possession.","TEN","LEG","RL",True,"NR","Missing context: governing tenancy law on entry and eviction. "+N_RENT),
R("RT","MEDIUM","The Tenant shall be responsible for all repairs to the Premises, including structural repairs and repairs necessitated by ordinary wear and tear.","Shifts structural and wear-and-tear repair costs to the Tenant, which departs from usual allocation.","TEN","FIN","RL",True,"NR","Missing context: rent level and any default statutory allocation. "+N_TPA),
R("RT","HIGH","The security deposit, equal to six (6) months' rent, shall be forfeited in full if the Tenant vacates before the end of the term, and the Landlord may in addition retain any rent paid in advance.","Large deposit forfeited in full plus advance rent retained, regardless of actual loss.","TEN","FIN","RL",False,"NR",N_S74),
# ---- CONSUMER_RIGHTS
R("CR","LOW","If you cancel your order before it is shipped, we will refund the full amount to your original payment method within seven (7) working days. Where a product is defective on delivery, you may request a replacement or refund within ten (10) days of receipt.","Clear cancellation refund, defect remedy and timelines.","CON","NONE","CS",False,"NR",CAND+"Consumer Protection (E-Commerce) Rules, 2020 and Consumer Protection Act, 2019; verify applicability and sections."),
R("CR","MEDIUM","Fees paid for the subscription are non-refundable, except where we are unable to provide the Service for reasons attributable to us, in which case we will refund the fees for the period of non-availability.","Refund limited to outages the Company attributes to itself, with no dispute mechanism.","CON","FIN","TC"),
R("CR","HIGH","All sales are final. The Company shall not be liable to refund or replace any product or service under any circumstances, including defects, deficiency of service or non-delivery, and the User waives all rights under any consumer protection law.","Blanket denial of remedies including defects and non-delivery plus a waiver of statutory rights.","CON","LEG","CS",False,"NR",N_CPA),
R("CR","MEDIUM","Approved refunds will be issued as store credit valid for ninety (90) days unless you request a refund to the original payment method, which may take up to forty-five (45) days.","Default store credit with expiry and slow cash refund; consumer must act to get money back.","CON","FIN","CS"),
# ---- CONSENT
R("CN","LOW","We will collect your location data only if you choose to enable location access in your device settings, and only to show nearby services. You can disable this at any time without affecting your ability to use other features.","Opt-in, purpose-limited, revocable and non-coercive.","DPR","NONE","PP",False,"NR",N_DPDP),
R("CN","MEDIUM","By continuing to use the Service, you consent to receive promotional communications from us and our partners by SMS, email and phone call.","Consent inferred from continued use and extended to unnamed partners.","CON","PRI","TC",False,"NR",CAND+"telecom commercial-communication rules and the DPDP Act, 2023 (status to be verified)."),
R("CN","HIGH","You irrevocably and unconditionally consent to the collection, use, storage and transfer of all your personal data, including biometric data, for any current or future purpose, and agree that no further consent shall be required.","Irrevocable blanket consent covering sensitive data and future purposes.","DPR","PRI","PP",False,"NR",N_DPDP),
R("CN","MEDIUM","The Employee authorises the Company to conduct background verification through third-party agencies, including verification of previous employment and educational records, and consents to the Company sharing the results with its clients where required by a client contract.","Verification is legitimate, but sharing results with clients is open-ended.","EMP","PRI","EM",True,"NR","Missing context: categories of data shared and safeguards. "+N_DPDP),
# ---- OTHER
R("OT","LOW","If any provision of this Agreement is held to be invalid or unenforceable, the remaining provisions shall continue in full force and effect, and the parties shall negotiate in good faith to replace the invalid provision with a valid one that most closely reflects their original intent.","Standard mutual severability clause.","BOTH","NONE","SA"),
R("OT","MEDIUM","The Company may amend these Terms at any time by posting the amended Terms on its website, and your continued use of the Service constitutes acceptance of the amendments.","Unilateral amendment with deemed acceptance and no direct notice.","CON","CTR","TC"),
]

FIELDS = ["id","clause_text","clause_category","risk_level","risk_reason","affected_party",
    "risk_type","jurisdiction","contract_type","context_required","legal_reference",
    "legal_reference_status","review_status","generation_source","split_group_id","notes"]

def build():
    recs = []
    for i, (cat, risk, text, reason, party, rtype, ctype, ctx, ref, notes, grp) in enumerate(ROWS, 1):
        rid = f"JSIN_{i:06d}"
        recs.append(dict(
            id=rid, clause_text=text, clause_category=CAT[cat], risk_level=risk,
            risk_reason=reason, affected_party=PARTY[party], risk_type=RT_[rtype],
            jurisdiction="INDIA", contract_type=CT[ctype], context_required=bool(ctx),
            legal_reference=None,
            legal_reference_status="NEEDS_REVIEW" if ref == "NR" else "NOT_APPLICABLE",
            review_status="SYNTHETIC_UNREVIEWED", generation_source="SYNTHETIC_AI",
            split_group_id="SG_" + (grp if grp else f"{i:06d}"), notes=notes))
    return recs

def shingles(t, n=5):
    w = re.findall(r"[a-z0-9']+", t.lower())
    return {tuple(w[i:i+n]) for i in range(max(1, len(w)-n+1))}

def validate(recs):
    errs = []
    ids = [r["id"] for r in recs]
    if len(set(ids)) != len(ids): errs.append("duplicate ids")
    cats = set(CAT.values()); parties = set(PARTY.values()); cts = set(CT.values()); rts = set(RT_.values())
    for r in recs:
        if list(r.keys()) != FIELDS: errs.append(f"{r['id']}: field set/order")
        if r["clause_category"] not in cats: errs.append(f"{r['id']}: category")
        if r["risk_level"] not in ("LOW","MEDIUM","HIGH"): errs.append(f"{r['id']}: risk")
        if r["affected_party"] not in parties: errs.append(f"{r['id']}: party")
        if r["risk_type"] not in rts: errs.append(f"{r['id']}: risk_type")
        if r["contract_type"] not in cts: errs.append(f"{r['id']}: contract_type")
        if (r["risk_level"] == "LOW") != (r["risk_type"] == "NONE"): errs.append(f"{r['id']}: risk_type vs level")
        if r["jurisdiction"] != "INDIA" or r["generation_source"] != "SYNTHETIC_AI": errs.append(f"{r['id']}: constants")
        if not isinstance(r["context_required"], bool): errs.append(f"{r['id']}: ctx type")
        if r["legal_reference"] is not None: errs.append(f"{r['id']}: legal_reference must be null in pilot")
        if (r["context_required"] or r["legal_reference_status"] == "NEEDS_REVIEW") and not r["notes"]: errs.append(f"{r['id']}: notes required")
        if len(r["clause_text"].split()) < 12 or not r["risk_reason"]: errs.append(f"{r['id']}: empty/short text")
        if re.search(r"[*#`|]", r["clause_text"]): errs.append(f"{r['id']}: markdown chars")
    near = []
    sh = [shingles(r["clause_text"]) for r in recs]
    for a, b in itertools.combinations(range(len(recs)), 2):
        if recs[a]["clause_text"].strip().lower() == recs[b]["clause_text"].strip().lower():
            errs.append(f"exact duplicate {recs[a]['id']} {recs[b]['id']}")
        j = len(sh[a] & sh[b]) / max(1, len(sh[a] | sh[b]))
        if j >= 0.5: near.append((recs[a]["id"], recs[b]["id"], round(j, 2)))
    return errs, near

def main(out="."):
    recs = build()
    errs, near = validate(recs)
    with open(f"{out}/jurisscan_pilot_v0.1.jsonl", "w", encoding="utf-8") as f:
        for r in recs: f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(f"{out}/jurisscan_pilot_v0.1.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS); w.writeheader()
        for r in recs:
            row = dict(r); row["context_required"] = str(r["context_required"]).lower()
            w.writerow(row)
    # round-trip parse check
    parsed = [json.loads(l) for l in open(f"{out}/jurisscan_pilot_v0.1.jsonl", encoding="utf-8")]
    assert parsed == recs
    lens = [len(r["clause_text"].split()) for r in recs]
    manifest = dict(
        batch=1, version="0.1-pilot", record_count=len(recs), id_range=[recs[0]["id"], recs[-1]["id"]],
        by_category=dict(sorted(Counter(r["clause_category"] for r in recs).items())),
        by_risk=dict(Counter(r["risk_level"] for r in recs)),
        by_contract_type=dict(sorted(Counter(r["contract_type"] for r in recs).items())),
        by_affected_party=dict(sorted(Counter(r["affected_party"] for r in recs).items())),
        category_x_risk={c: dict(Counter(r["risk_level"] for r in recs if r["clause_category"] == c)) for c in sorted({r["clause_category"] for r in recs})},
        needs_legal_review=sum(r["legal_reference_status"] == "NEEDS_REVIEW" for r in recs),
        context_required=sum(r["context_required"] for r in recs),
        legal_references_asserted=0,
        review_status="all SYNTHETIC_UNREVIEWED",
        words_per_clause=dict(min=min(lens), median=sorted(lens)[len(lens)//2], max=max(lens)),
        shared_split_groups=sum(1 for c in Counter(r["split_group_id"] for r in recs).values() if c > 1),
        validation=dict(errors=errs, near_duplicate_pairs_jaccard5gram_ge_0_5=near,
            checks=["unique ids","field set and order","enum membership","type checks","risk_type vs risk_level","notes required for context/NEEDS_REVIEW","legal_reference null","exact duplicates","5-word-shingle near duplicates","JSONL round-trip parse"],
            disclaimer="Automated structural checks only. Not legal validation."))
    json.dump(manifest, open(f"{out}/manifest_batch_001.json", "w"), indent=2)
    print(json.dumps({k: manifest[k] for k in ("record_count","by_risk","by_contract_type","needs_legal_review","context_required","words_per_clause","shared_split_groups")}, indent=1))
    print("errors:", errs); print("near-dups:", near)
    return 1 if errs else 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "."))
