"""Realistic legal document fixtures for segmentation tests.

These are purpose-written, representative examples (not copied from any real
contract) covering the document types JurisScan targets: residential tenancy,
employment, privacy policy, website terms and a master services agreement, plus
a subscription agreement that mixes Roman numerals and bullet lists.

They intentionally exercise a range of numbering styles — numbered sections,
nested decimals, Roman numerals, lettered and parenthesised subclauses, bullets,
unnumbered paragraphs, preambles and irregular formatting — so segmentation can
be verified against realistic wording rather than toy strings.
"""

from __future__ import annotations

RENTAL_AGREEMENT = """RESIDENTIAL TENANCY AGREEMENT

This Agreement is made on 1 April 2026 between the Landlord and the Tenant.

1. The Landlord lets the Premises to the Tenant for the Term at the Rent.

2. Rent
2.1 The Tenant shall pay the Rent in advance on the first day of each month.
2.2 If any Rent remains unpaid for fourteen (14) days the Landlord may charge interest.

3. Obligations of the Tenant
(a) to keep the interior of the Premises in good repair;
(b) to pay all charges for utilities consumed at the Premises;
(c) not to assign or sublet without the Landlord's written consent.

4. Deposit
The Deposit shall be held in a government-approved tenancy deposit scheme.

5. Termination
Either party may terminate this Agreement by giving two months' written notice.
"""

EMPLOYMENT_CONTRACT = """CONTRACT OF EMPLOYMENT

This contract is between the Employer and the Employee.

1. Appointment and Duties
1.1 The Employee is employed as a Senior Analyst with effect from the Start Date.
1.2 The Employee shall perform such duties as the Employer may reasonably require.

2. Remuneration
2.1 The Employer shall pay the Employee a salary of 60,000 per annum.
2.2 Salary is paid monthly in arrears on the last working day of each month.
2.3 The Employee shall not be entitled to overtime pay.

3. Confidentiality and Intellectual Property
(a) The Employee shall not disclose Confidential Information to any person.
(b) All intellectual property created by the Employee vests in the Employer.

4. Restrictive Covenants
4.1 The Employee shall not compete with the Employer for six months after termination.
4.2 The Employee shall not solicit any client of the Employer during that period.

5. Termination
The Employer may terminate the employment by giving the Employee 7 days notice.
"""

PRIVACY_POLICY = """PRIVACY POLICY

Last updated: 1 April 2026.

1. Introduction
We are committed to protecting your personal data and respecting your privacy.

2. Data We Collect
2.1 We collect information you provide when you create an account.
2.2 We collect technical information such as your IP address and browser type.

3. How We Use Your Data
3.1 We use your personal data to provide and improve our services.
3.2 We process personal data on the basis of your consent and our legitimate interests.

4. Your Rights
(a) You have the right to access the personal data we hold about you.
(b) You have the right to request that we rectify inaccurate personal data.
(c) You have the right to request erasure of your personal data.

5. Data Retention
We retain personal data only for as long as necessary for the purposes described above.
"""

TERMS_AND_CONDITIONS = """TERMS AND CONDITIONS OF SERVICE

Please read these terms carefully before using our website.

1. Acceptance of Terms
By accessing this website you agree to be bound by these Terms and Conditions.

2. Use of the Website
2.1 You agree to use the website only for lawful purposes.
2.2 You must not misuse the website by introducing viruses or harmful material.

3. Intellectual Property
3.1 All content on this website is owned by us or our licensors.
3.2 You may not reproduce any content without our prior written permission.

4. Limitation of Liability
(a) We do not exclude liability for death or personal injury caused by negligence.
(b) Subject to paragraph (a), our total liability shall not exceed the fees paid.

5. Governing Law
These terms are governed by the laws of England and Wales.
"""

SERVICE_AGREEMENT = """MASTER SERVICES AGREEMENT

This Master Services Agreement is entered into between the Supplier and the Customer.

1. Definitions and Interpretation
In this Agreement the following definitions apply unless the context requires otherwise.

2. Services
2.1 The Supplier shall provide the Services described in each Statement of Work.
2.2 Delivery
2.2.1 The Supplier shall perform the Services with reasonable skill and care.
2.2.2 The Supplier shall comply with all applicable laws and regulations.
2.3 The Customer shall provide such information as the Supplier reasonably requires.

3. Payment
3.1 The Customer shall pay the fees set out in the relevant Statement of Work.
3.2 The Customer shall pay each valid invoice within sixty (60) days of receipt.

4. Indemnity
The Supplier shall indemnify the Customer against all claims arising from the Services.

5. Term and Termination
Either party may terminate this Agreement for convenience on 30 days written notice.
"""

# Roman numerals, a bullet list and a trailing unnumbered paragraph.
SUBSCRIPTION_AGREEMENT = """SUBSCRIPTION AGREEMENT

This Subscription Agreement governs your access to the Platform.

1. Grant of Rights
1.1 Subject to payment of the fees we grant you a non-exclusive right to use the Platform.
(i) The licence is limited to your internal business purposes;
(ii) The licence does not permit resale of the Platform.

2. Restrictions
You shall not:
- copy the Platform except as permitted by applicable law;
- reverse engineer or decompile the Platform;
- remove any proprietary notices from the Platform.

3. Fees
3.1 Fees are payable annually in advance unless otherwise agreed in writing.
"""

ROOMMATE_AGREEMENT = """SHARED HOUSE AGREEMENT

This Agreement is made between the residents of the Property on 1 May 2026.

1. Rent and Bills
1.1 Each resident shall pay an equal share of the Rent on the first day of the month.
1.2 Each resident shall contribute to the utility bills in equal shares.

2. House Rules
(a) Residents shall keep all shared areas reasonably clean and tidy;
(b) Residents shall not keep pets at the Property without written consent.

3. Quiet Enjoyment
Each resident shall be entitled to quiet enjoyment of the Property.

4. Disputes
If a dispute arises the residents shall first attempt to resolve it between themselves.
"""

ALL_FIXTURES = {
    "rental": RENTAL_AGREEMENT,
    "employment": EMPLOYMENT_CONTRACT,
    "privacy": PRIVACY_POLICY,
    "terms": TERMS_AND_CONDITIONS,
    "service": SERVICE_AGREEMENT,
    "subscription": SUBSCRIPTION_AGREEMENT,
    "roommate": ROOMMATE_AGREEMENT,
}
