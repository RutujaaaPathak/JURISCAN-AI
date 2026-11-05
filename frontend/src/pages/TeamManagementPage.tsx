import {
  AlertCircle,
  AlertTriangle,
  Building2,
  Check,
  CheckCircle2,
  Copy,
  Mail,
  Plus,
  RefreshCw,
  Search,
  Shield,
  Trash2,
  UserCheck,
  UserCog,
  UserPlus,
  Users,
} from "lucide-react"
import { useCallback, useEffect, useState } from "react"

import { EmptyState, ErrorState, LoadingSkeleton } from "@/components/common/States"
import { StatCard } from "@/components/dashboard/StatCard"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select } from "@/components/ui/select"
import { Spinner } from "@/components/ui/spinner"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useToast } from "@/components/ui/toast"
import { useAuth } from "@/lib/auth"
import type { CompanyRole } from "@/lib/auth"
import {
  createInvitation,
  getTeamOverview,
  listInvitations,
  listTeamMembers,
  removeTeamMember,
  revokeInvitation,
  updateMemberRole,
} from "@/lib/company"
import type {
  InvitationCreateResponse,
  InvitationRead,
  TeamMemberRead,
  TeamOverview,
} from "@/lib/company"
import {
  COMPANY_ROLE_META,
  filterTeamMembers,
  formatCompanyRole,
} from "@/lib/companyFilters"
import { formatDate } from "@/lib/format"

export function TeamManagementPage() {
  const { user } = useAuth()
  const { toast } = useToast()

  const isCompanyAdmin = user?.company_role === "COMPANY_ADMIN"

  // Data states
  const [overview, setOverview] = useState<TeamOverview | null>(null)
  const [loadingOverview, setLoadingOverview] = useState(true)

  const [members, setMembers] = useState<TeamMemberRead[]>([])
  const [loadingMembers, setLoadingMembers] = useState(true)
  const [membersError, setMembersError] = useState<string | null>(null)

  const [invitations, setInvitations] = useState<InvitationRead[]>([])
  const [loadingInvitations, setLoadingInvitations] = useState(true)

  // Filters
  const [search, setSearch] = useState("")
  const [roleFilter, setRoleFilter] = useState("ALL")

  // Invite modal state
  const [inviteModalOpen, setInviteModalOpen] = useState(false)
  const [inviteEmail, setInviteEmail] = useState("")
  const [inviteRole, setInviteRole] = useState<CompanyRole>("MEMBER")
  const [submittingInvite, setSubmittingInvite] = useState(false)
  const [inviteResult, setInviteResult] = useState<InvitationCreateResponse | null>(null)
  const [copiedLink, setCopiedLink] = useState(false)

  // Role change modal state
  const [roleModalMember, setRoleModalMember] = useState<TeamMemberRead | null>(null)
  const [targetRole, setTargetRole] = useState<CompanyRole>("MEMBER")
  const [updatingRole, setUpdatingRole] = useState(false)

  // Removal confirmation dialog state
  const [removeModalMember, setRemoveModalMember] = useState<TeamMemberRead | null>(null)
  const [removingMember, setRemovingMember] = useState(false)

  // Revoke invitation modal state
  const [revokeTargetInvitation, setRevokeTargetInvitation] = useState<InvitationRead | null>(null)
  const [revoking, setRevoking] = useState(false)

  const loadData = useCallback(async () => {
    setLoadingOverview(true)
    setLoadingMembers(true)
    setLoadingInvitations(true)
    setMembersError(null)

    try {
      const [overviewData, membersData, invitationsData] = await Promise.all([
        getTeamOverview().catch(() => null),
        listTeamMembers(),
        listInvitations().catch(() => ({ items: [], total: 0 })),
      ])
      if (overviewData) setOverview(overviewData)
      setMembers(membersData.items)
      setInvitations(invitationsData.items)
    } catch (err) {
      setMembersError(err instanceof Error ? err.message : "Failed to load team data.")
    } finally {
      setLoadingOverview(false)
      setLoadingMembers(false)
      setLoadingInvitations(false)
    }
  }, [])

  useEffect(() => {
    void loadData()
  }, [loadData])

  const handleCreateInvite = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!inviteEmail.trim()) return

    setSubmittingInvite(true)
    try {
      const res = await createInvitation({
        email: inviteEmail.trim(),
        company_role: inviteRole,
      })
      setInviteResult(res)
      setInviteEmail("")
      setInviteRole("MEMBER")
      toast({
        title: "Invitation created",
        description: `Invitation generated for ${res.invitation.email}.`,
      })
      void loadData()
    } catch (err) {
      toast({
        title: "Could not create invitation",
        description: err instanceof Error ? err.message : "Request failed.",
        variant: "destructive",
      })
    } finally {
      setSubmittingInvite(false)
    }
  }

  const handleUpdateRole = async () => {
    if (!roleModalMember) return
    setUpdatingRole(true)
    try {
      await updateMemberRole(roleModalMember.user_id, targetRole)
      toast({
        title: "Role updated",
        description: `Updated ${roleModalMember.full_name || roleModalMember.email}'s role to ${formatCompanyRole(targetRole)}.`,
      })
      setRoleModalMember(null)
      void loadData()
    } catch (err) {
      toast({
        title: "Role update failed",
        description: err instanceof Error ? err.message : "Failed to update role.",
        variant: "destructive",
      })
    } finally {
      setUpdatingRole(false)
    }
  }

  const handleRemoveMember = async () => {
    if (!removeModalMember) return
    setRemovingMember(true)
    try {
      await removeTeamMember(removeModalMember.user_id)
      toast({
        title: "Member removed",
        description: `Removed ${removeModalMember.full_name || removeModalMember.email} from company team.`,
      })
      setRemoveModalMember(null)
      void loadData()
    } catch (err) {
      toast({
        title: "Removal failed",
        description: err instanceof Error ? err.message : "Failed to remove member.",
        variant: "destructive",
      })
    } finally {
      setRemovingMember(false)
    }
  }

  const handleRevokeInvitation = async () => {
    if (!revokeTargetInvitation) return
    setRevoking(true)
    try {
      await revokeInvitation(revokeTargetInvitation.id)
      toast({
        title: "Invitation revoked",
        description: `Invitation for ${revokeTargetInvitation.email} has been revoked.`,
      })
      setRevokeTargetInvitation(null)
      void loadData()
    } catch (err) {
      toast({
        title: "Could not revoke invitation",
        description: err instanceof Error ? err.message : "Failed to revoke invitation.",
        variant: "destructive",
      })
    } finally {
      setRevoking(false)
    }
  }

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text).then(() => {
      setCopiedLink(true)
      setTimeout(() => setCopiedLink(false), 2500)
      toast({
        title: "Copied to clipboard",
        description: "Invitation link copied.",
      })
    })
  }

  const filteredMembers = filterTeamMembers(members, search, roleFilter)

  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-6 p-4 md:p-6">
      {/* Header */}
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-2xl font-semibold tracking-tight md:text-3xl text-foreground">
              Team Management
            </h1>
            {overview?.company.name && (
              <Badge variant="outline" className="border-primary/30 text-primary">
                <Building2 className="size-3 mr-1" />
                {overview.company.name}
              </Badge>
            )}
          </div>
          <p className="text-sm text-muted-foreground mt-1">
            Manage your company workspace members, team permissions, and single-use invitations.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => void loadData()}
            disabled={loadingMembers}
            className="border-white/10 hover:border-primary/40"
          >
            <RefreshCw className={`size-3.5 mr-1.5 ${loadingMembers ? "animate-spin" : ""}`} />
            Refresh
          </Button>

          {isCompanyAdmin && (
            <Button
              size="sm"
              onClick={() => {
                setInviteResult(null)
                setInviteModalOpen(true)
              }}
              className="bg-primary text-primary-foreground hover:bg-primary/90 font-medium"
            >
              <UserPlus className="size-3.5 mr-1.5" />
              Invite Member
            </Button>
          )}
        </div>
      </div>

      {/* Role Notice */}
      {!isCompanyAdmin && (
        <Alert className="border-amber-500/20 bg-amber-500/5 py-3 text-xs text-amber-300">
          <AlertCircle className="size-4 text-amber-400" />
          <AlertTitle className="text-xs font-semibold">Read-Only View</AlertTitle>
          <AlertDescription className="text-xs">
            You are logged in with the <span className="font-semibold">{formatCompanyRole(user?.company_role)}</span> role.
            Only Company Administrators can invite team members, adjust roles, or revoke memberships.
          </AlertDescription>
        </Alert>
      )}

      {/* Stat Cards */}
      <div className="grid gap-3 grid-cols-2 sm:grid-cols-4">
        <StatCard
          label="Total Members"
          value={overview?.total_members ?? (loadingOverview ? "—" : 0)}
          icon={Users}
          hint="Enrolled in workspace"
        />
        <StatCard
          label="Active Accounts"
          value={overview?.active_members ?? (loadingOverview ? "—" : 0)}
          icon={UserCheck}
          tone="success"
          hint="Can access documents"
        />
        <StatCard
          label="Pending Invites"
          value={overview?.pending_invitations ?? (loadingOverview ? "—" : 0)}
          icon={Mail}
          tone={overview && overview.pending_invitations > 0 ? "warning" : "default"}
          hint="Awaiting onboarding"
        />
        <StatCard
          label="Admins"
          value={overview?.role_counts?.COMPANY_ADMIN ?? (loadingOverview ? "—" : 0)}
          icon={Shield}
          hint="Workspace owners"
        />
      </div>

      {/* Main Tabs */}
      <Tabs defaultValue="members" className="w-full">
        <TabsList className="bg-muted/40 border border-border/40">
          <TabsTrigger value="members" className="text-xs">
            Team Members ({members.length})
          </TabsTrigger>
          <TabsTrigger value="invitations" className="text-xs">
            Invitations ({invitations.length})
          </TabsTrigger>
        </TabsList>

        {/* Tab 1: Members */}
        <TabsContent value="members" className="mt-4 flex flex-col gap-4">
          {/* Search & Filter */}
          <Card className="border-border/60 bg-card/60 backdrop-blur-sm">
            <CardContent className="p-3.5 flex flex-wrap items-center justify-between gap-3">
              <div className="relative flex-1 min-w-[240px]">
                <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
                <Input
                  placeholder="Search members by name or email..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="pl-9 bg-background/50 text-sm h-9"
                />
              </div>

              <div className="flex items-center gap-2">
                <Label className="text-xs text-muted-foreground whitespace-nowrap">Filter Role:</Label>
                <div className="w-[160px]">
                  <Select value={roleFilter} onChange={(e) => setRoleFilter(e.target.value)}>
                    <option value="ALL">All Roles</option>
                    <option value="COMPANY_ADMIN">Company Admin</option>
                    <option value="MANAGER">Manager</option>
                    <option value="MEMBER">Member</option>
                    <option value="VIEWER">Viewer</option>
                  </Select>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Members Table */}
          <Card className="border-border/60 bg-card/40">
            <CardContent className="p-0">
              {loadingMembers ? (
                <div className="p-6">
                  <LoadingSkeleton rows={5} />
                </div>
              ) : membersError ? (
                <div className="p-6">
                  <ErrorState
                    title="Could not load team members"
                    description={membersError}
                    onRetry={() => void loadData()}
                  />
                </div>
              ) : filteredMembers.length === 0 ? (
                <div className="p-8">
                  <EmptyState
                    icon={Users}
                    title="No team members found"
                    description={search ? "No members match your search criteria." : "Invite colleagues to collaborate in your workspace."}
                  />
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow className="border-border/40 hover:bg-transparent">
                        <TableHead>Member</TableHead>
                        <TableHead>Email</TableHead>
                        <TableHead>Role</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Joined</TableHead>
                        {isCompanyAdmin && <TableHead className="text-right">Actions</TableHead>}
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {filteredMembers.map((member) => {
                        const initials = (member.full_name || member.email)
                          .split(" ")
                          .map((n) => n[0])
                          .join("")
                          .slice(0, 2)
                          .toUpperCase()

                        return (
                          <TableRow key={member.user_id} className="border-border/30 hover:bg-muted/30">
                            <TableCell>
                              <div className="flex items-center gap-3">
                                <div className="flex size-9 shrink-0 items-center justify-center rounded-full bg-primary/10 border border-primary/20 text-primary text-xs font-semibold">
                                  {initials}
                                </div>
                                <div className="min-w-0">
                                  <p className="truncate text-sm font-medium text-foreground flex items-center gap-1.5">
                                    {member.full_name || "—"}
                                    {member.is_self && (
                                      <Badge variant="secondary" className="text-[10px] py-0 px-1">
                                        You
                                      </Badge>
                                    )}
                                  </p>
                                </div>
                              </div>
                            </TableCell>

                            <TableCell className="text-xs text-muted-foreground font-mono">
                              {member.email}
                            </TableCell>

                            <TableCell>
                              <Badge
                                variant={
                                  member.company_role === "COMPANY_ADMIN"
                                    ? "default"
                                    : member.company_role === "MANAGER"
                                      ? "secondary"
                                      : "outline"
                                }
                                className="text-[11px] font-medium"
                              >
                                {formatCompanyRole(member.company_role)}
                              </Badge>
                            </TableCell>

                            <TableCell>
                              <Badge
                                variant={member.account_status === "ACTIVE" ? "outline" : "secondary"}
                                className={`text-[10px] ${
                                  member.account_status === "ACTIVE"
                                    ? "text-emerald-400 border-emerald-500/30 bg-emerald-500/5"
                                    : "text-muted-foreground"
                                }`}
                              >
                                {member.account_status}
                              </Badge>
                            </TableCell>

                            <TableCell className="text-xs text-muted-foreground">
                              {formatDate(member.joined_at)}
                            </TableCell>

                            {isCompanyAdmin && (
                              <TableCell className="text-right">
                                <div className="flex items-center justify-end gap-1.5">
                                  <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={() => {
                                      setRoleModalMember(member)
                                      setTargetRole(member.company_role)
                                    }}
                                    className="h-8 text-xs border-white/10 hover:border-primary/40"
                                  >
                                    <UserCog className="size-3.5 mr-1" />
                                    Change Role
                                  </Button>
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={() => setRemoveModalMember(member)}
                                    className="h-8 text-xs text-red-400 hover:text-red-300 hover:bg-red-500/10"
                                    title="Remove member"
                                  >
                                    <Trash2 className="size-3.5" />
                                  </Button>
                                </div>
                              </TableCell>
                            )}
                          </TableRow>
                        )
                      })}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Tab 2: Invitations */}
        <TabsContent value="invitations" className="mt-4">
          <Card className="border-border/60 bg-card/40">
            <CardHeader className="flex flex-row items-center justify-between pb-3">
              <div>
                <CardTitle className="text-base font-semibold">Workspace Invitations</CardTitle>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Single-use cryptographic invitations with expiration tracking.
                </p>
              </div>
              {isCompanyAdmin && (
                <Button
                  size="sm"
                  onClick={() => {
                    setInviteResult(null)
                    setInviteModalOpen(true)
                  }}
                  className="bg-primary text-primary-foreground hover:bg-primary/90 text-xs"
                >
                  <Plus className="size-3.5 mr-1" />
                  New Invite
                </Button>
              )}
            </CardHeader>
            <CardContent className="p-0">
              {loadingInvitations ? (
                <div className="p-6">
                  <LoadingSkeleton rows={4} />
                </div>
              ) : invitations.length === 0 ? (
                <div className="p-8">
                  <EmptyState
                    icon={Mail}
                    title="No invitations pending"
                    description="When you invite team members, pending and previous invitations appear here."
                  />
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow className="border-border/40 hover:bg-transparent">
                        <TableHead>Invitee Email</TableHead>
                        <TableHead>Assigned Role</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Invited By</TableHead>
                        <TableHead>Expires</TableHead>
                        {isCompanyAdmin && <TableHead className="text-right">Actions</TableHead>}
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {invitations.map((inv) => (
                        <TableRow key={inv.id} className="border-border/30 hover:bg-muted/30">
                          <TableCell className="font-mono text-xs font-medium text-foreground">
                            {inv.email}
                          </TableCell>

                          <TableCell>
                            <Badge variant="outline" className="text-[11px]">
                              {formatCompanyRole(inv.company_role)}
                            </Badge>
                          </TableCell>

                          <TableCell>
                            <Badge
                              variant={
                                inv.status === "PENDING"
                                  ? "default"
                                  : inv.status === "ACCEPTED"
                                    ? "outline"
                                    : "secondary"
                              }
                              className={`text-[10px] ${
                                inv.status === "ACCEPTED"
                                  ? "text-emerald-400 border-emerald-500/30"
                                  : inv.status === "REVOKED" || inv.status === "EXPIRED"
                                    ? "text-muted-foreground"
                                    : ""
                              }`}
                            >
                              {inv.status}
                            </Badge>
                          </TableCell>

                          <TableCell className="text-xs text-muted-foreground">
                            {inv.invited_by_name || "—"}
                          </TableCell>

                          <TableCell className="text-xs text-muted-foreground">
                            {formatDate(inv.expires_at)}
                          </TableCell>

                          {isCompanyAdmin && (
                            <TableCell className="text-right">
                              {inv.status === "PENDING" && !inv.is_expired && (
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => setRevokeTargetInvitation(inv)}
                                  className="h-7 text-xs text-red-400 hover:text-red-300 hover:bg-red-500/10"
                                >
                                  Revoke
                                </Button>
                              )}
                            </TableCell>
                          )}
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Invite Member Dialog */}
      <Dialog open={inviteModalOpen} onOpenChange={setInviteModalOpen}>
        <DialogContent className="max-w-md bg-card border-border/80">
          <DialogHeader>
            <DialogTitle className="text-lg font-semibold text-foreground">
              Invite Team Member
            </DialogTitle>
            <DialogDescription className="text-xs text-muted-foreground">
              Send a secure workspace onboarding invitation.
            </DialogDescription>
          </DialogHeader>

          {inviteResult ? (
            <div className="flex flex-col gap-4 py-3">
              <Alert className="border-emerald-500/30 bg-emerald-500/10 text-emerald-300">
                <CheckCircle2 className="size-4 text-emerald-400" />
                <AlertTitle className="text-xs font-semibold">Invitation Generated</AlertTitle>
                <AlertDescription className="text-xs">
                  A secure, single-use token was minted for{" "}
                  <strong className="text-foreground">{inviteResult.invitation.email}</strong> as{" "}
                  <strong className="text-foreground">{formatCompanyRole(inviteResult.invitation.company_role)}</strong>.
                </AlertDescription>
              </Alert>

              <div className="rounded-lg border border-border/60 bg-background/50 p-3 flex flex-col gap-2">
                <p className="text-xs font-medium text-foreground">
                  Email Delivery Notice:
                </p>
                <p className="text-xs text-muted-foreground leading-relaxed">
                  Email delivery is not configured in this local development environment.
                  Copy and send the direct onboarding link below to your team member:
                </p>

                {inviteResult.development_accept_url && (
                  <div className="mt-1 flex items-center gap-2">
                    <Input
                      readOnly
                      value={inviteResult.development_accept_url}
                      className="text-xs font-mono bg-muted/30 h-8 select-all"
                    />
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => copyToClipboard(inviteResult.development_accept_url!)}
                      className="h-8 shrink-0 text-xs"
                    >
                      {copiedLink ? <Check className="size-3.5 text-emerald-400 mr-1" /> : <Copy className="size-3.5 mr-1" />}
                      {copiedLink ? "Copied" : "Copy Link"}
                    </Button>
                  </div>
                )}
              </div>

              <DialogFooter className="mt-2">
                <Button
                  size="sm"
                  onClick={() => {
                    setInviteResult(null)
                    setInviteModalOpen(false)
                  }}
                  className="w-full bg-primary text-primary-foreground hover:bg-primary/90"
                >
                  Done
                </Button>
              </DialogFooter>
            </div>
          ) : (
            <form onSubmit={handleCreateInvite} className="flex flex-col gap-4 py-3">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="invite-email" className="text-xs font-medium text-foreground">
                  Email Address
                </Label>
                <Input
                  id="invite-email"
                  type="email"
                  required
                  placeholder="colleague@yourcompany.com"
                  value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
                  className="bg-background/50 text-sm h-9"
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <Label className="text-xs font-medium text-foreground">Assign Role</Label>
                <Select value={inviteRole} onChange={(e) => setInviteRole(e.target.value as CompanyRole)}>
                  <option value="COMPANY_ADMIN">Company Admin (Full access & team mgmt)</option>
                  <option value="MANAGER">Manager (Manage documents & reports)</option>
                  <option value="MEMBER">Member (Upload & analyze contracts)</option>
                  <option value="VIEWER">Viewer (Read-only document access)</option>
                </Select>
                <p className="text-[11px] text-muted-foreground mt-0.5">
                  {COMPANY_ROLE_META[inviteRole].description}
                </p>
              </div>

              <DialogFooter className="mt-3 flex sm:justify-between items-center gap-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setInviteModalOpen(false)}
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  size="sm"
                  disabled={submittingInvite || !inviteEmail.trim()}
                  className="bg-primary text-primary-foreground hover:bg-primary/90"
                >
                  {submittingInvite ? <Spinner className="size-3.5 mr-1.5" /> : <UserPlus className="size-3.5 mr-1.5" />}
                  Generate Invitation
                </Button>
              </DialogFooter>
            </form>
          )}
        </DialogContent>
      </Dialog>

      {/* Role Change Dialog */}
      <Dialog open={roleModalMember !== null} onOpenChange={(open) => !open && setRoleModalMember(null)}>
        <DialogContent className="max-w-md bg-card border-border/80">
          <DialogHeader>
            <DialogTitle className="text-lg font-semibold text-foreground">
              Change Team Role
            </DialogTitle>
            <DialogDescription className="text-xs text-muted-foreground">
              Modify permissions for {roleModalMember?.full_name || roleModalMember?.email}.
            </DialogDescription>
          </DialogHeader>

          <div className="flex flex-col gap-4 py-3">
            <div className="flex flex-col gap-1.5">
              <Label className="text-xs font-medium text-foreground">New Role</Label>
              <Select value={targetRole} onChange={(e) => setTargetRole(e.target.value as CompanyRole)}>
                <option value="COMPANY_ADMIN">Company Admin</option>
                <option value="MANAGER">Manager</option>
                <option value="MEMBER">Member</option>
                <option value="VIEWER">Viewer</option>
              </Select>
              <p className="text-[11px] text-muted-foreground mt-1">
                {COMPANY_ROLE_META[targetRole].description}
              </p>
            </div>

            {roleModalMember?.company_role === "COMPANY_ADMIN" && targetRole !== "COMPANY_ADMIN" && (
              <Alert className="border-amber-500/30 bg-amber-500/10 text-amber-300 py-2.5">
                <AlertTriangle className="size-4 text-amber-400" />
                <AlertTitle className="text-xs font-semibold">Demoting Administrator</AlertTitle>
                <AlertDescription className="text-xs">
                  Ensure at least one other active Company Admin remains. The system prevents removing the last admin.
                </AlertDescription>
              </Alert>
            )}
          </div>

          <DialogFooter className="flex sm:justify-between items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setRoleModalMember(null)}
              disabled={updatingRole}
            >
              Cancel
            </Button>
            <Button
              size="sm"
              onClick={() => void handleUpdateRole()}
              disabled={updatingRole || targetRole === roleModalMember?.company_role}
              className="bg-primary text-primary-foreground hover:bg-primary/90"
            >
              {updatingRole && <Spinner className="size-3.5 mr-1.5" />}
              Save Changes
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Remove Member Confirmation Dialog */}
      <Dialog open={removeModalMember !== null} onOpenChange={(open) => !open && setRemoveModalMember(null)}>
        <DialogContent className="max-w-md bg-card border-border/80">
          <DialogHeader>
            <DialogTitle className="text-lg font-semibold text-red-400 flex items-center gap-2">
              <AlertTriangle className="size-5" />
              Remove Member
            </DialogTitle>
            <DialogDescription className="text-xs text-muted-foreground">
              Are you sure you want to remove{" "}
              <strong className="text-foreground">{removeModalMember?.full_name || removeModalMember?.email}</strong> from
              the company workspace?
            </DialogDescription>
          </DialogHeader>

          <p className="text-xs text-muted-foreground leading-relaxed py-2">
            This will immediately revoke their workspace access, permissions, and association with company contracts.
            The last company administrator cannot be removed.
          </p>

          <DialogFooter className="flex sm:justify-between items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setRemoveModalMember(null)}
              disabled={removingMember}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              size="sm"
              onClick={() => void handleRemoveMember()}
              disabled={removingMember}
            >
              {removingMember && <Spinner className="size-3.5 mr-1.5" />}
              Confirm Removal
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Revoke Invitation Dialog */}
      <Dialog open={revokeTargetInvitation !== null} onOpenChange={(open) => !open && setRevokeTargetInvitation(null)}>
        <DialogContent className="max-w-md bg-card border-border/80">
          <DialogHeader>
            <DialogTitle className="text-lg font-semibold text-foreground">
              Revoke Invitation
            </DialogTitle>
            <DialogDescription className="text-xs text-muted-foreground">
              Are you sure you want to revoke the invitation for{" "}
              <strong className="text-foreground">{revokeTargetInvitation?.email}</strong>?
            </DialogDescription>
          </DialogHeader>

          <p className="text-xs text-muted-foreground py-2">
            The single-use invitation link will be permanently invalidated.
          </p>

          <DialogFooter className="flex sm:justify-between items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setRevokeTargetInvitation(null)}
              disabled={revoking}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              size="sm"
              onClick={() => void handleRevokeInvitation()}
              disabled={revoking}
            >
              {revoking && <Spinner className="size-3.5 mr-1.5" />}
              Revoke Invite
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
export default TeamManagementPage
