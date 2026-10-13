import { CalendarDays } from "lucide-react"
import { Route, Routes } from "react-router-dom"

import { RequireAuth, RequireRole, RedirectIfAuthenticated } from "@/components/auth/guards"
import { AuthProvider } from "@/context/AuthProvider"
import { RoleProvider } from "@/context/RoleContext"
import { DashboardLayout } from "@/layouts/DashboardLayout"
import { MainLayout } from "@/layouts/MainLayout"
import { ScrollToTop } from "@/components/layout/ScrollToTop"
import { AnalysisDetailPage } from "@/pages/AnalysisDetailPage"
import { AnalysisReportsPage } from "@/pages/AnalysisReportsPage"
import { AvailableCasesPage } from "@/pages/AvailableCasesPage"
import { CaseDetailPage } from "@/pages/CaseDetailPage"
import { DashboardPage } from "@/pages/DashboardPage"
import { DocumentsPage } from "@/pages/DocumentsPage"
import { FindLawyerPage } from "@/pages/FindLawyerPage"
import { HomePage } from "@/pages/HomePage"
import { LawyerProfilePage } from "@/pages/LawyerProfilePage"
import { PrivacyPage, TermsPage } from "@/pages/LegalPage"
import { LoginPage } from "@/pages/LoginPage"
import { MessagesPage } from "@/pages/MessagesPage"
import { MyCasesPage } from "@/pages/MyCasesPage"
import { MyLegalCasesPage } from "@/pages/MyLegalCasesPage"
import { NotificationsPage } from "@/pages/NotificationsPage"
import { NotFoundPage } from "@/pages/NotFoundPage"
import { PlaceholderPage } from "@/pages/PlaceholderPage"
import { PostCasePage } from "@/pages/PostCasePage"
import { RegisterPage } from "@/pages/RegisterPage"
import { SettingsPage } from "@/pages/SettingsPage"
import { SignUpPage } from "@/pages/SignUpPage"
import { UploadPage } from "@/pages/UploadPage"

function App() {
  return (
    <AuthProvider>
      <RoleProvider>
        <ScrollToTop />
        <Routes>
          <Route element={<MainLayout />}>
            <Route index element={<HomePage />} />
            <Route
              path="login"
              element={
                <RedirectIfAuthenticated>
                  <LoginPage />
                </RedirectIfAuthenticated>
              }
            />
            <Route
              path="signup"
              element={
                <RedirectIfAuthenticated>
                  <SignUpPage />
                </RedirectIfAuthenticated>
              }
            />
            <Route
              path="signup/:role"
              element={
                <RedirectIfAuthenticated>
                  <RegisterPage />
                </RedirectIfAuthenticated>
              }
            />
            <Route path="privacy" element={<PrivacyPage />} />
            <Route path="terms" element={<TermsPage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Route>
          <Route
            path="/dashboard"
            element={
              <RequireAuth>
                <DashboardLayout />
              </RequireAuth>
            }
          >
            <Route index element={<DashboardPage />} />
            <Route
              path="client"
              element={
                <RequireRole roles={["individual"]}>
                  <DashboardPage />
                </RequireRole>
              }
            />
            <Route
              path="company"
              element={
                <RequireRole roles={["company"]}>
                  <DashboardPage />
                </RequireRole>
              }
            />
            <Route
              path="lawyer"
              element={
                <RequireRole roles={["lawyer"]}>
                  <DashboardPage />
                </RequireRole>
              }
            />
            <Route path="upload" element={<UploadPage />} />
            <Route path="documents" element={<DocumentsPage />} />
            <Route path="reports" element={<AnalysisReportsPage />} />
            <Route
              path="legal-help"
              element={
                <RequireRole roles={["individual"]}>
                  <FindLawyerPage />
                </RequireRole>
              }
            />
            <Route
              path="post-case"
              element={
                <RequireRole roles={["individual"]}>
                  <PostCasePage />
                </RequireRole>
              }
            />
            <Route
              path="legal-cases"
              element={
                <RequireRole roles={["individual"]}>
                  <MyLegalCasesPage />
                </RequireRole>
              }
            />
            <Route
              path="available-cases"
              element={
                <RequireRole roles={["lawyer"]}>
                  <AvailableCasesPage />
                </RequireRole>
              }
            />
            <Route
              path="my-cases"
              element={
                <RequireRole roles={["lawyer"]}>
                  <MyCasesPage />
                </RequireRole>
              }
            />
            <Route path="cases/:id" element={<CaseDetailPage />} />
            <Route
              path="profile"
              element={
                <RequireRole roles={["lawyer"]}>
                  <LawyerProfilePage />
                </RequireRole>
              }
            />
            <Route path="messages" element={<MessagesPage />} />
            <Route
              path="calendar"
              element={
                <RequireRole roles={["lawyer"]}>
                  <PlaceholderPage
                    title="Calendar"
                    description="Hearings, deadlines and consultations in one place."
                    icon={CalendarDays}
                    notice="Consultations are proposed and confirmed inside each assigned case's workspace. A consolidated calendar view that aggregates them is not implemented yet."
                    emptyTitle="No events"
                    emptyDescription="A calendar view of your case consultations will appear here once available."
                  />
                </RequireRole>
              }
            />
            <Route
              path="notifications"
              element={
                <RequireRole roles={["lawyer", "individual"]}>
                  <NotificationsPage />
                </RequireRole>
              }
            />
            <Route path="analyses/:id" element={<AnalysisDetailPage />} />
            <Route path="settings" element={<SettingsPage />} />
          </Route>
        </Routes>
      </RoleProvider>
    </AuthProvider>
  )
}

export default App
