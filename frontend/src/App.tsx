import { CalendarDays } from "lucide-react"
import { Route, Routes } from "react-router-dom"

import { RoleProvider } from "@/context/RoleContext"
import { DashboardLayout } from "@/layouts/DashboardLayout"
import { MainLayout } from "@/layouts/MainLayout"
import { AnalysisDetailPage } from "@/pages/AnalysisDetailPage"
import { AnalysisReportsPage } from "@/pages/AnalysisReportsPage"
import { AvailableCasesPage } from "@/pages/AvailableCasesPage"
import { CaseDetailPage } from "@/pages/CaseDetailPage"
import { DashboardPage } from "@/pages/DashboardPage"
import { DocumentsPage } from "@/pages/DocumentsPage"
import { FindLawyerPage } from "@/pages/FindLawyerPage"
import { HomePage } from "@/pages/HomePage"
import { LawyerProfilePage } from "@/pages/LawyerProfilePage"
import { MessagesPage } from "@/pages/MessagesPage"
import { MyCasesPage } from "@/pages/MyCasesPage"
import { MyLegalCasesPage } from "@/pages/MyLegalCasesPage"
import { NotificationsPage } from "@/pages/NotificationsPage"
import { NotFoundPage } from "@/pages/NotFoundPage"
import { PlaceholderPage } from "@/pages/PlaceholderPage"
import { PostCasePage } from "@/pages/PostCasePage"
import { SettingsPage } from "@/pages/SettingsPage"
import { UploadPage } from "@/pages/UploadPage"

function App() {
  return (
    <RoleProvider>
      <Routes>
        <Route element={<MainLayout />}>
          <Route index element={<HomePage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
        <Route path="/dashboard" element={<DashboardLayout />}>
          <Route index element={<DashboardPage />} />
          <Route path="upload" element={<UploadPage />} />
          <Route path="documents" element={<DocumentsPage />} />
          <Route path="reports" element={<AnalysisReportsPage />} />
          <Route path="legal-help" element={<FindLawyerPage />} />
          <Route path="post-case" element={<PostCasePage />} />
          <Route path="legal-cases" element={<MyLegalCasesPage />} />
          <Route path="available-cases" element={<AvailableCasesPage />} />
          <Route path="my-cases" element={<MyCasesPage />} />
          <Route path="cases/:id" element={<CaseDetailPage />} />
          <Route path="profile" element={<LawyerProfilePage />} />
          <Route path="messages" element={<MessagesPage />} />
          <Route
            path="calendar"
            element={
              <PlaceholderPage
                title="Calendar"
                description="Hearings, deadlines and consultations in one place."
                icon={CalendarDays}
                notice="Consultations are proposed and confirmed inside each assigned case's workspace. A consolidated calendar view that aggregates them is not implemented yet."
                emptyTitle="No events"
                emptyDescription="A calendar view of your case consultations will appear here once available."
              />
            }
          />
          <Route
            path="notifications"
            element={<NotificationsPage />}
          />
          <Route path="analyses/:id" element={<AnalysisDetailPage />} />
          <Route path="settings" element={<SettingsPage />} />
        </Route>
      </Routes>
    </RoleProvider>
  )
}

export default App
