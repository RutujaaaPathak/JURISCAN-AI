import type { ReactNode } from "react"
import { Link } from "react-router-dom"

import { Button } from "@/components/ui/button"

function LegalLayout({
  title,
  summary,
  children,
}: {
  title: string
  summary: string
  children: ReactNode
}) {
  return (
    <div className="mx-auto w-full max-w-3xl px-4 py-14 sm:px-6 sm:py-20">
      <p className="text-xs font-semibold tracking-[0.2em] text-[#c5a868] uppercase">Legal</p>
      <h1 className="mt-3 text-4xl font-semibold tracking-tight text-foreground">{title}</h1>
      <p className="mt-4 text-lg text-muted-foreground leading-relaxed">{summary}</p>
      <p className="mt-4 text-sm text-muted-foreground">
        Placeholder values are marked in square brackets and must be confirmed before public launch.
      </p>
      <div className="mt-10 flex flex-col gap-8">{children}</div>
      <div className="mt-12 border-t border-white/[0.08] pt-8">
        <Button asChild variant="outline" className="btn-dark-secondary">
          <Link to="/">Back to home</Link>
        </Button>
      </div>
    </div>
  )
}

function Section({ heading, children }: { heading: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-xl font-semibold tracking-tight">{heading}</h2>
      <div className="flex flex-col gap-3 text-sm leading-relaxed text-muted-foreground">
        {children}
      </div>
    </section>
  )
}

export function PrivacyPage() {
  return (
    <LegalLayout
      title="Privacy Policy"
      summary="How JurisScan-AI collects, uses and protects the information you provide when you use the service."
    >
      <p className="text-sm text-muted-foreground">Last updated: [date to be confirmed]</p>

      <Section heading="Who we are">
        <p>
          JurisScan-AI (the "Service") is operated by [legal entity name] ("we", "us"). This policy
          explains what we collect, why we collect it and the choices you have. You can reach us at
          [privacy contact email].
        </p>
      </Section>

      <Section heading="Information you give us">
        <ul className="flex list-disc flex-col gap-2 pl-5">
          <li>
            Account details: your name, email address, role, and a password. Passwords are stored
            only as a salted hash, never in plain text.
          </li>
          <li>
            Optional profile details such as your organization name or jurisdiction, where the
            workspace you use collects them.
          </li>
          <li>
            Content you upload: legal documents and the text, clauses, findings and analyses derived
            from them.
          </li>
          <li>Content you create in the Service, such as cases, messages and notifications.</li>
        </ul>
      </Section>

      <Section heading="Information collected automatically">
        <p>
          When you use the Service we record basic technical information needed to operate it, such
          as request logs and error information. The Service does not use advertising or
          third-party tracking cookies. Your browser stores a small amount of local data: your
          theme preference and your session token, which keeps you signed in.
        </p>
      </Section>

      <Section heading="How we use your information">
        <ul className="flex list-disc flex-col gap-2 pl-5">
          <li>To provide the Service, including running document analyses and storing results.</li>
          <li>To authenticate you and keep your account and workspace secure.</li>
          <li>To send service messages such as notifications and email digests you enable.</li>
          <li>To maintain the reliability, safety and integrity of the Service.</li>
        </ul>
      </Section>

      <Section heading="Sharing">
        <p>
          We do not sell your personal information. We share it only with service providers that
          help us run the Service (for example hosting and email delivery), and only as needed to
          provide it. Current providers: [list of subprocessors to be confirmed]. We may disclose
          information where required by law.
        </p>
      </Section>

      <Section heading="Retention">
        <p>
          We keep account and content data for as long as your account is active or as needed to
          provide the Service. You can delete documents from your workspace, and you can request
          deletion of your account. Retention periods: [retention period to be confirmed].
        </p>
      </Section>

      <Section heading="Security">
        <p>
          We protect accounts with hashed passwords and token-based sessions, and we restrict access
          to data by role. How data is encrypted at rest and in transit depends on the hosting
          environment: [security and hosting specifics to be confirmed].
        </p>
      </Section>

      <Section heading="Your rights">
        <p>
          Depending on where you live, you may have the right to access, correct, export or delete
          your personal information, and to object to certain processing. To exercise these rights,
          contact us at [privacy contact email].
        </p>
      </Section>

      <Section heading="Children">
        <p>The Service is not intended for anyone under 18.</p>
      </Section>

      <Section heading="Changes to this policy">
        <p>
          We may update this policy from time to time. When we do, we will revise the "last updated"
          date above.
        </p>
      </Section>
    </LegalLayout>
  )
}

export function TermsPage() {
  return (
    <LegalLayout
      title="Terms of Service"
      summary="The rules for using JurisScan-AI, including important limits on what the analysis can do."
    >
      <p className="text-sm text-muted-foreground">Last updated: [date to be confirmed]</p>

      <Section heading="Acceptance">
        <p>
          By creating an account or using JurisScan-AI (the "Service"), you agree to these Terms. If
          you use the Service for an organization, you confirm you have authority to accept these
          Terms for that organization.
        </p>
      </Section>

      <Section heading="Not legal advice">
        <p>
          JurisScan-AI is a document-review tool. It does not provide legal advice, and using it
          does not create a lawyer-client relationship. Its findings are informational only. Always
          have important documents reviewed by a qualified lawyer before relying on them.
        </p>
      </Section>

      <Section heading="What the analysis can and cannot do">
        <p>
          The analysis is rule-based and transparent: it applies defined checks to the text of a
          document and reports what it finds. It can miss issues, and it can flag things that turn
          out not to matter. Treat every finding as a prompt to review, not as a final conclusion.
        </p>
      </Section>

      <Section heading="Your account">
        <p>
          You are responsible for the accuracy of your account details, for keeping your password
          secure, and for all activity under your account. Provide accurate information and use a
          workspace that matches your role.
        </p>
      </Section>

      <Section heading="Acceptable use">
        <p>
          Do not use the Service to break the law, to process content you do not have the right to
          process, to attempt to disrupt or gain unauthorized access to the Service, or to infringe
          the rights of others.
        </p>
      </Section>

      <Section heading="Your content">
        <p>
          You keep ownership of the documents and content you upload. You grant us the limited
          permission needed to store and process that content to provide the Service, including
          running analyses and showing results back to you and the people you share a workspace
          with.
        </p>
      </Section>

      <Section heading="Our content">
        <p>
          The Service, including its software, design and branding, is owned by us or our licensors
          and is protected by law. These Terms do not grant you any rights to our trademarks or
          branding.
        </p>
      </Section>

      <Section heading="Availability and third parties">
        <p>
          The Service is provided on an "as is" and "as available" basis. We do not guarantee that
          it will be uninterrupted or error free, and we may change or discontinue features.
        </p>
      </Section>

      <Section heading="Disclaimers and liability">
        <p>
          To the fullest extent permitted by law, we disclaim all warranties not expressly stated
          here, and our total liability arising from the Service is limited to [liability cap to be
          confirmed]. Some jurisdictions do not allow certain limitations, so parts of this section
          may not apply to you.
        </p>
      </Section>

      <Section heading="Termination">
        <p>
          You may stop using the Service at any time. We may suspend or end access if you violate
          these Terms or if we need to protect the Service or other users.
        </p>
      </Section>

      <Section heading="Governing law">
        <p>These Terms are governed by the laws of [jurisdiction to be confirmed].</p>
      </Section>

      <Section heading="Changes and contact">
        <p>
          We may update these Terms, and will revise the "last updated" date when we do. Questions?
          Contact [contact email].
        </p>
      </Section>
    </LegalLayout>
  )
}
