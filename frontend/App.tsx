import { FormEvent, ReactElement, useEffect, useState } from "react";
import "./auth.css";
import "./platform.css";
import "./styles.css";

const API_URL = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000/api";
const TOKEN_KEY = "forge_owner_token";
const PLATFORM_TOKEN_KEY = "forge_platform_token";
type Portal = "owner" | "member";
type OwnerView = "overview" | "members" | "retention";
type MemberView = "home" | "plan" | "progress";
type Goal = "lose-weight" | "build-muscle" | "get-lean";

interface Member {
  id: number; name: string; phone: string; email: string; package: string;
  expires_on: string; days_left: number; status: "active" | "expiring" | "expired";
}
interface Meal { time: string; name: string; detail: string; calories: number }
interface Workout { week: number; theme: string; sessions: string[]; target: string }
interface Plan {
  goal_label: string; focus: string; daily_calories: number; daily_protein_g: number;
  water_liters: number; bmi: number; meals: Meal[]; workouts: Workout[]; note: string;
}
interface Progress { id: number; weight_kg: number; recorded_on: string }
interface Branch { id: number; name: string }
interface AuthUser { id: number; name: string; role: string; active_branch_id: number; branches: Branch[] }
interface AuthState { gym: { id: number; name: string; workspace_slug: string; multi_branch_enabled: boolean }; user: AuthUser }
interface DashboardSummary {
  members: { total: number; active: number; expiring_this_week: number; expired: number };
  retention: { reminders_sent_last_7_days: number };
  revenue: { monthly: number | null; renewal_rate: number | null; note: string };
  insight: { title: string; detail: string; action_enabled: boolean; expiring_member_ids: number[] };
}
interface PlatformGym {
  id: number; name: string; workspace_slug: string; account_status: "active" | "suspended";
  sales_channel: string; multi_branch_enabled: boolean; branches: Branch[];
  owners: { id: number; name: string; phone: string; is_active: boolean }[];
}

const icons: Record<string, ReactElement> = {
  grid: <><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" /></>,
  users: <><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75" /></>,
  bell: <><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9" /><path d="M13.73 21a2 2 0 0 1-3.46 0" /></>,
  plus: <><path d="M12 5v14M5 12h14" /></>,
  arrow: <><path d="M5 12h14M13 6l6 6-6 6" /></>,
  whatsapp: <><path d="M21 11.5a8.4 8.4 0 0 1-9 8.4 8.6 8.6 0 0 1-3.8-1.1L3 20l1.3-5a8.5 8.5 0 1 1 16.7-3.5Z" /><path d="M8.4 7.8c.2-.3.4-.4.7-.4h.4c.2 0 .4.1.5.4l.7 1.6c.1.3.1.5-.1.7l-.6.7c.8 1.5 1.8 2.4 3.3 3l.6-.7c.2-.2.4-.3.7-.2l1.7.8c.3.1.4.3.4.5v.4c0 .4-.2.7-.5.9-.6.4-1.4.6-2.1.4-3.4-.9-6.2-3.4-7.2-6.7-.2-.5 0-1 .5-1.4Z" /></>,
  chart: <><path d="M3 3v18h18" /><path d="m7 15 4-4 3 3 5-6" /></>,
  flame: <><path d="M12 22c4 0 7-3 7-7 0-3-2-5-3-6-1 3-3 4-4 2-1-2 1-4-1-7-1 3-6 5-6 11 0 4 3 7 7 7Z" /></>,
  dumbbell: <><path d="m6.5 6.5 11 11M21 21l-1-1M3 3l1 1M18 22l4-4M2 6l4-4M3 10l7-7M14 21l7-7" /></>,
  target: <><circle cx="12" cy="12" r="9" /><circle cx="12" cy="12" r="5" /><circle cx="12" cy="12" r="1" /></>,
  calendar: <><rect x="3" y="4" width="18" height="17" rx="2" /><path d="M8 2v4M16 2v4M3 10h18" /></>,
  logout: <><path d="M10 17l5-5-5-5M15 12H3M21 19V5a2 2 0 0 0-2-2h-6" /></>,
};
function Icon({ name, size = 18 }: { name: string; size?: number }) {
  return <svg className="icon" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">{icons[name]}</svg>;
}

const fallbackMembers: Member[] = [
  { id: 1, name: "Aarav Sharma", phone: "+91 98765 42010", email: "aarav@example.com", package: "Strength Annual", expires_on: "2026-06-02", days_left: 2, status: "expiring" },
  { id: 2, name: "Maya Patel", phone: "+91 98765 42011", email: "maya@example.com", package: "Transform 3 Month", expires_on: "2026-06-05", days_left: 5, status: "expiring" },
  { id: 5, name: "Kabir Singh", phone: "+91 98765 42014", email: "kabir@example.com", package: "Transform 3 Month", expires_on: "2026-06-07", days_left: 7, status: "expiring" },
  { id: 3, name: "Rohan Mehta", phone: "+91 98765 42012", email: "rohan@example.com", package: "Open Gym Monthly", expires_on: "2026-06-18", days_left: 18, status: "active" },
  { id: 4, name: "Isha Verma", phone: "+91 98765 42013", email: "isha@example.com", package: "Strength Annual", expires_on: "2026-09-02", days_left: 94, status: "active" },
  { id: 6, name: "Diya Kapoor", phone: "+91 98765 42015", email: "diya@example.com", package: "Open Gym Monthly", expires_on: "2026-05-28", days_left: -3, status: "expired" },
];
const fallbackPlan: Plan = {
  goal_label: "Get lean", focus: "body recomposition", daily_calories: 2200, daily_protein_g: 148, water_liters: 2.7, bmi: 24.6,
  meals: [
    { time: "07:30", name: "Protein-first breakfast", detail: "Eggs or paneer, oats, seasonal fruit", calories: 528 },
    { time: "12:45", name: "Balanced lunch", detail: "Lean protein, rice or roti, vegetables, curd", calories: 748 },
    { time: "16:30", name: "Training snack", detail: "Fruit, yogurt, and a small handful of nuts", calories: 308 },
    { time: "20:00", name: "Recovery dinner", detail: "Protein, cooked vegetables, and a lighter carb portion", calories: 616 },
  ],
  workouts: [
    { week: 1, theme: "Build the base", sessions: ["Full body strength", "Zone 2 cardio + mobility", "Upper body + core", "Lower body technique"], target: "Move with control and finish fresh." },
    { week: 2, theme: "Add volume", sessions: ["Lower body strength", "Upper body strength", "Intervals + core", "Full body circuit"], target: "Add one working set to main lifts." },
    { week: 3, theme: "Progressive push", sessions: ["Lower body progressive", "Upper body progressive", "Conditioning intervals", "Full body strength"], target: "Increase load slightly while keeping form." },
    { week: 4, theme: "Consolidate", sessions: ["Full body strength", "Cardio + mobility", "Upper and core", "Lower and conditioning"], target: "Repeat your strongest week with clean reps." },
  ], note: "This starter plan is general fitness guidance. Adjust with a qualified coach for injuries or medical needs."
};
const fallbackProgress: Progress[] = [
  { id: 1, weight_kg: 82.4, recorded_on: "2026-02-28" }, { id: 2, weight_kg: 80.6, recorded_on: "2026-03-30" },
  { id: 3, weight_kg: 78.9, recorded_on: "2026-04-30" }, { id: 4, weight_kg: 77.8, recorded_on: "2026-05-31" },
];

async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const token = localStorage.getItem(TOKEN_KEY);
  const response = await fetch(`${API_URL}${path}`, { ...options, headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}), ...options?.headers } });
  if (!response.ok) throw new Error((await response.json().catch(() => null))?.detail ?? "API request failed");
  return response.json();
}
async function platformApi<T>(path: string, options?: RequestInit): Promise<T> {
  const token = localStorage.getItem(PLATFORM_TOKEN_KEY);
  const response = await fetch(`${API_URL}${path}`, { ...options, headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}), ...options?.headers } });
  if (!response.ok) throw new Error((await response.json().catch(() => null))?.detail ?? "API request failed");
  return response.json();
}
function initials(name: string) { return name.split(" ").map((word) => word[0]).join("").slice(0, 2); }
function formatDate(value: string) { return new Intl.DateTimeFormat("en", { day: "numeric", month: "short" }).format(new Date(`${value}T00:00:00`)); }

export default function App() {
  if (window.location.pathname.startsWith("/platform")) return <PlatformApp />;
  const [auth, setAuth] = useState<AuthState | null>(null);
  const [checkingAuth, setCheckingAuth] = useState(Boolean(localStorage.getItem(TOKEN_KEY)));
  const [portal, setPortal] = useState<Portal>("owner");
  const [ownerView, setOwnerView] = useState<OwnerView>("overview");
  const [memberView, setMemberView] = useState<MemberView>("home");
  const [members, setMembers] = useState<Member[]>([]);
  const [plan, setPlan] = useState<Plan>(fallbackPlan);
  const [progress, setProgress] = useState<Progress[]>(fallbackProgress);
  const [toast, setToast] = useState("");
  useEffect(() => { if (!checkingAuth) return; api<AuthState>("/auth/me").then(setAuth).catch(() => localStorage.removeItem(TOKEN_KEY)).finally(() => setCheckingAuth(false)); }, [checkingAuth]);
  useEffect(() => { if (!auth) return; api<Member[]>("/members").then(setMembers).catch(() => undefined); }, [auth?.user.active_branch_id]);
  useEffect(() => { if (!toast) return; const timeout = setTimeout(() => setToast(""), 2600); return () => clearTimeout(timeout); }, [toast]);
  async function logout() { try { await api("/auth/logout", { method: "POST" }); } finally { localStorage.removeItem(TOKEN_KEY); setAuth(null); } }
  async function selectBranch(branch_id: number) { await api("/auth/select-branch", { method: "POST", body: JSON.stringify({ branch_id }) }); setAuth((current) => current ? { ...current, user: { ...current.user, active_branch_id: branch_id } } : current); }
  if (checkingAuth) return <div className="auth-loading">Loading Forge...</div>;
  if (!auth) return <AuthScreen onAuthenticated={(nextAuth, token) => { localStorage.setItem(TOKEN_KEY, token); setAuth(nextAuth); }} />;
  return <div className="app-shell">
    {toast && <div className="toast"><span>âœ“</span>{toast}</div>}
    {portal === "owner"
      ? <OwnerPortal auth={auth} members={members} setMembers={setMembers} view={ownerView} setView={setOwnerView} showToast={setToast} switchPortal={() => setPortal("member")} logout={logout} selectBranch={selectBranch} />
      : <MemberPortal view={memberView} setView={setMemberView} plan={plan} setPlan={setPlan} progress={progress} setProgress={setProgress} showToast={setToast} switchPortal={() => setPortal("owner")} />}
  </div>;
}

function AuthScreen({ onAuthenticated }: { onAuthenticated: (auth: AuthState, token: string) => void }) {
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [login, setLogin] = useState({ workspace_slug: "", phone: "", password: "" });
  const [signup, setSignup] = useState({ gym_name: "", owner_name: "", phone: "", password: "", branches: ["Main Branch"] });
  async function submit(event: FormEvent) {
    event.preventDefault(); setError(""); setBusy(true);
    try {
      const payload = await api<{ token: string; gym?: AuthState["gym"]; user: AuthUser }>(mode === "login" ? "/auth/login" : "/auth/signup", { method: "POST", body: JSON.stringify(mode === "login" ? login : signup) });
      const auth = payload.gym ? { gym: payload.gym, user: payload.user } : await api<AuthState>("/auth/me", { headers: { Authorization: `Bearer ${payload.token}` } });
      onAuthenticated(auth, payload.token);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to continue"); } finally { setBusy(false); }
  }
  return <div className="auth-page"><form className="auth-card" onSubmit={submit}><Brand /><small>{mode === "login" ? "GYM WORKSPACE LOGIN" : "CREATE YOUR GYM WORKSPACE"}</small><h1>{mode === "login" ? "Welcome back" : "Set up Forge for your gym"}</h1><p>{mode === "login" ? "Use your gym workspace and phone number to continue." : "Start with one branch or add more for a multi-branch setup."}</p>{mode === "login" ? <><label>Workspace slug<input required value={login.workspace_slug} onChange={(e) => setLogin({ ...login, workspace_slug: e.target.value })} placeholder="e.g. forge-fitness" /></label><label>Phone number<input required value={login.phone} onChange={(e) => setLogin({ ...login, phone: e.target.value })} placeholder="+91 98765 43210" /></label><label>Password<input required type="password" value={login.password} onChange={(e) => setLogin({ ...login, password: e.target.value })} /></label></> : <><label>Gym name<input required value={signup.gym_name} onChange={(e) => setSignup({ ...signup, gym_name: e.target.value })} /></label><label>Owner name<input required value={signup.owner_name} onChange={(e) => setSignup({ ...signup, owner_name: e.target.value })} /></label><label>Phone number<input required value={signup.phone} onChange={(e) => setSignup({ ...signup, phone: e.target.value })} /></label><label>Password<input required minLength={8} type="password" value={signup.password} onChange={(e) => setSignup({ ...signup, password: e.target.value })} /></label><label>Branches<input required value={signup.branches.join(", ")} onChange={(e) => setSignup({ ...signup, branches: e.target.value.split(",").map((value) => value.trim()).filter(Boolean) })} placeholder="Main Branch, Indiranagar" /><span>Separate multiple branches with commas.</span></label></>}{error && <div className="auth-error">{error}</div>}<button className="primary-btn auth-submit" disabled={busy}>{busy ? "Please wait..." : mode === "login" ? "Log in" : "Create workspace"}</button><button type="button" className="auth-switch" onClick={() => setMode(mode === "login" ? "signup" : "login")}>{mode === "login" ? "New gym? Create a workspace" : "Already registered? Log in"}</button></form></div>;
}

function Brand() { return <div className="brand"><div className="brand-mark">F</div><div><strong>FORGE</strong><span>PERFORMANCE CLUB</span></div></div>; }
function OwnerPortal({ auth, members, setMembers, view, setView, showToast, switchPortal, logout, selectBranch }: { auth: AuthState; members: Member[]; setMembers: (members: Member[]) => void; view: OwnerView; setView: (view: OwnerView) => void; showToast: (toast: string) => void; switchPortal: () => void; logout: () => void; selectBranch: (id: number) => void }) {
  const [showAdd, setShowAdd] = useState(false);
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const expiring = members.filter((member) => member.days_left >= 0 && member.days_left <= 7);
  const active = members.filter((member) => member.status !== "expired").length;
  async function refresh() { try { setMembers(await api<Member[]>("/members")); setSummary(await api<DashboardSummary>("/dashboard/summary")); } catch { /* keep current state */ } }
  useEffect(() => { refresh(); }, [auth.user.active_branch_id]);
  async function remind(id?: number) {
    try { await api(id ? `/reminders/${id}` : "/reminders/expiring", { method: "POST" }); } catch { /* demo mode */ }
    showToast(id ? "WhatsApp reminder queued" : `${expiring.length} WhatsApp reminders queued`);
  }
  return <div className="owner-layout">
    <aside className="sidebar">
      <Brand />
      {auth.user.branches.length > 1 && <select className="branch-select" value={auth.user.active_branch_id} onChange={(event) => selectBranch(Number(event.target.value))}>{auth.user.branches.map((branch) => <option value={branch.id} key={branch.id}>{branch.name}</option>)}</select>}
      <nav>
        <button className={view === "overview" ? "active" : ""} onClick={() => setView("overview")}><Icon name="grid" />Overview</button>
        <button className={view === "members" ? "active" : ""} onClick={() => setView("members")}><Icon name="users" />Members<span>{members.length}</span></button>
        <button className={view === "retention" ? "active" : ""} onClick={() => setView("retention")}><Icon name="bell" />Retention<span className="alert-count">{expiring.length}</span></button>
      </nav>
      <div className="sidebar-bottom">
        <button onClick={switchPortal}><Icon name="arrow" />Member preview</button>
        <button onClick={logout}><Icon name="logout" />Log out</button>
        <div className="owner-profile"><div className="avatar">{initials(auth.user.name)}</div><div><strong>{auth.user.name}</strong><small>{auth.user.role.replace("_", " ")}</small></div></div>
      </div>
    </aside>
    <main className="owner-main">
      <header className="topbar"><div><small>{auth.gym.name}</small><h1>{view === "overview" ? `Welcome, ${auth.user.name}` : view === "members" ? "Member directory" : "Retention center"}</h1></div><button className="primary-btn" onClick={() => setShowAdd(true)}><Icon name="plus" size={16} />Add member</button></header>
      {view === "overview" && <OwnerOverview members={members} active={active} expiring={expiring} summary={summary} remind={remind} setView={setView} />}
      {view === "members" && <MemberDirectory members={members} remind={remind} />}
      {view === "retention" && <Retention members={expiring} remind={remind} />}
    </main>
    {showAdd && <AddMember onClose={() => setShowAdd(false)} onSaved={() => { refresh(); setShowAdd(false); showToast("Member added successfully"); }} />}
  </div>;
}
function OwnerOverview({ members, active, expiring, summary, remind, setView }: { members: Member[]; active: number; expiring: Member[]; summary: DashboardSummary | null; remind: (id?: number) => void; setView: (view: OwnerView) => void }) {
  const recent = members.slice(0, 4);
  const memberStats = summary?.members;
  const revenueValue = summary?.revenue.monthly == null ? "No data" : `Rs ${summary.revenue.monthly.toLocaleString("en-IN")}`;
  const renewalValue = summary?.revenue.renewal_rate == null ? "No data" : `${summary.revenue.renewal_rate}%`;
  return <section>
    <div className="metric-grid">
      <Metric label="Active members" value={(memberStats?.active ?? active).toString()} change={`${memberStats?.expired ?? 0} expired`} icon="users" tone="lime" />
      <Metric label="Expiring this week" value={(memberStats?.expiring_this_week ?? expiring.length).toString()} change="Based on expiry dates" icon="bell" tone="amber" />
      <Metric label="Renewal rate" value={renewalValue} change="Needs payment history" icon="chart" tone="purple" />
      <Metric label="Monthly revenue" value={revenueValue} change="No estimates shown" icon="flame" tone="blue" />
    </div>
    <div className="dashboard-grid">
      <div className="panel expiring-panel"><PanelTitle eyebrow="Retention radar" title="Expiring this week" action="View all" onClick={() => setView("retention")} /><p className="panel-copy">Reach out before these memberships lapse.</p><div className="compact-list">{expiring.length ? expiring.map((member) => <CompactMember key={member.id} member={member} remind={remind} />) : <EmptyState text="No members are expiring in the next 7 days." />}</div></div>
      <div className="panel insight-panel"><div className="insight-top"><span className="pulse-dot" /><small>LIVE INSIGHT</small></div><h2>{summary?.insight.title ?? "Live insight will appear after the dashboard loads."}</h2><p>{summary?.insight.detail ?? "Forge processes member expiry, reminder, and payment data before showing recommendations."}</p>{summary?.insight.action_enabled && <button className="dark-btn" onClick={() => remind()}><Icon name="whatsapp" size={17} />Send all reminders</button>}</div>
    </div>
    <div className="panel recent-panel"><PanelTitle eyebrow="Member base" title="Recent memberships" action="Open directory" onClick={() => setView("members")} /><MemberTable members={recent} remind={remind} /></div>
  </section>;
}
function Metric({ label, value, change, icon, tone }: { label: string; value: string; change: string; icon: string; tone: string }) { return <div className="metric-card"><div className={`metric-icon ${tone}`}><Icon name={icon} /></div><div><small>{label}</small><strong>{value}</strong><span>{change}</span></div></div>; }
function PanelTitle({ eyebrow, title, action, onClick }: { eyebrow: string; title: string; action?: string; onClick?: () => void }) { return <div className="panel-title"><div><small>{eyebrow}</small><h2>{title}</h2></div>{action && <button onClick={onClick}>{action}<Icon name="arrow" size={15} /></button>}</div>; }
function CompactMember({ member, remind }: { member: Member; remind: (id?: number) => void }) { return <div className="compact-member"><div className="avatar soft">{initials(member.name)}</div><div><strong>{member.name}</strong><small>{member.package}</small></div><div className="expiry"><b>{member.days_left}d</b><small>left</small></div><button onClick={() => remind(member.id)}><Icon name="whatsapp" size={17} /></button></div>; }
function EmptyState({ text }: { text: string }) { return <div className="empty-state">{text}</div>; }
function MemberDirectory({ members, remind }: { members: Member[]; remind: (id: number) => void }) { const [search, setSearch] = useState(""); const filtered = members.filter((member) => member.name.toLowerCase().includes(search.toLowerCase())); return <section className="panel table-page"><div className="directory-head"><PanelTitle eyebrow="All records" title="Member directory" /><label className="search">âŒ•<input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search member" /></label></div><MemberTable members={filtered} remind={remind} /></section>; }
function MemberTable({ members, remind }: { members: Member[]; remind: (id: number) => void }) { return <div className="table-wrap"><table><thead><tr><th>Member</th><th>Package</th><th>Expiry</th><th>Status</th><th></th></tr></thead><tbody>{members.map((member) => <tr key={member.id}><td><div className="member-cell"><div className="avatar soft">{initials(member.name)}</div><div><strong>{member.name}</strong><small>{member.phone}</small></div></div></td><td>{member.package}</td><td>{formatDate(member.expires_on)}</td><td><span className={`status ${member.status}`}>{member.status}</span></td><td><button className="icon-btn" onClick={() => remind(member.id)}><Icon name="whatsapp" size={17} /></button></td></tr>)}</tbody></table></div>; }
function Retention({ members, remind }: { members: Member[]; remind: (id?: number) => void }) { return <section><div className="retention-hero"><div><small>WEEKLY RETENTION QUEUE</small><h2>Stay ahead of every expiry.</h2><p>{members.length} members are due for a thoughtful check-in this week.</p></div><button className="dark-btn" onClick={() => remind()}><Icon name="whatsapp" size={17} />Send all reminders</button></div><div className="panel"><PanelTitle eyebrow="Next 7 days" title="Members to contact" /><div className="retention-list">{members.map((member) => <div className="retention-row" key={member.id}><div className="avatar soft">{initials(member.name)}</div><div className="retention-name"><strong>{member.name}</strong><small>{member.phone}</small></div><div><small>Package</small><strong>{member.package}</strong></div><div><small>Expires</small><strong>{formatDate(member.expires_on)} Â· {member.days_left} days</strong></div><button className="outline-btn" onClick={() => remind(member.id)}><Icon name="whatsapp" size={16} />Remind</button></div>)}</div></div></section>; }
function AddMember({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const [form, setForm] = useState({ name: "", phone: "", email: "", package: "Transform 3 Month", expires_on: "2026-06-30" });
  async function submit(event: FormEvent) { event.preventDefault(); try { await api("/members", { method: "POST", body: JSON.stringify(form) }); } catch { /* preview submits without API */ } onSaved(); }
  return <div className="modal-backdrop"><form className="modal" onSubmit={submit}><button type="button" className="modal-close" onClick={onClose}>Ã—</button><small>NEW MEMBERSHIP</small><h2>Add a member</h2><p>Create their membership record and track the renewal date.</p><label>Full name<input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="e.g. Neha Rao" /></label><label>WhatsApp number<input required value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} placeholder="+91 98765 43210" /></label><label>Email<input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} placeholder="member@example.com" /></label><div className="form-row"><label>Package<select value={form.package} onChange={(e) => setForm({ ...form, package: e.target.value })}><option>Transform 3 Month</option><option>Strength Annual</option><option>Open Gym Monthly</option></select></label><label>Expires on<input required type="date" value={form.expires_on} onChange={(e) => setForm({ ...form, expires_on: e.target.value })} /></label></div><button className="primary-btn modal-submit">Add membership</button></form></div>;
}

function PlatformApp() {
  const [admin, setAdmin] = useState<{ id: number; name: string; phone: string } | null>(null);
  const [checking, setChecking] = useState(Boolean(localStorage.getItem(PLATFORM_TOKEN_KEY)));
  const [gyms, setGyms] = useState<PlatformGym[]>([]);
  const [error, setError] = useState("");
  useEffect(() => { if (!checking) return; platformApi<{ admin: { id: number; name: string; phone: string } }>("/platform/auth/me").then((payload) => setAdmin(payload.admin)).catch(() => localStorage.removeItem(PLATFORM_TOKEN_KEY)).finally(() => setChecking(false)); }, [checking]);
  async function refresh() { setGyms(await platformApi<PlatformGym[]>("/platform/gyms")); }
  useEffect(() => { if (admin) refresh().catch((reason) => setError(reason instanceof Error ? reason.message : "Unable to load gyms")); }, [admin]);
  async function logout() { try { await platformApi("/platform/auth/logout", { method: "POST" }); } finally { localStorage.removeItem(PLATFORM_TOKEN_KEY); setAdmin(null); } }
  if (checking) return <div className="auth-loading">Loading platform...</div>;
  if (!admin) return <PlatformLogin onLogin={(nextAdmin, token) => { localStorage.setItem(PLATFORM_TOKEN_KEY, token); setAdmin(nextAdmin); }} />;
  return <div className="platform-shell"><header className="platform-head"><div><small>HIDDEN PLATFORM CONTROL</small><h1>Forge admin</h1><p>Create direct-sales gym workspaces and control access.</p></div><button className="outline-btn" onClick={logout}>Log out</button></header>{error && <div className="auth-error">{error}</div>}<PlatformCreateGym onCreated={refresh} /><section className="panel"><PanelTitle eyebrow="Direct customers" title="Gym workspaces" /><div className="platform-list">{gyms.map((gym) => <PlatformGymRow key={gym.id} gym={gym} onChanged={refresh} />)}{!gyms.length && <EmptyState text="No gym workspaces created yet." />}</div></section></div>;
}

function PlatformLogin({ onLogin }: { onLogin: (admin: { id: number; name: string; phone: string }, token: string) => void }) {
  const [form, setForm] = useState({ phone: "", password: "" });
  const [error, setError] = useState("");
  async function submit(event: FormEvent) { event.preventDefault(); setError(""); try { const payload = await platformApi<{ token: string; admin: { id: number; name: string; phone: string } }>("/platform/auth/login", { method: "POST", body: JSON.stringify(form) }); onLogin(payload.admin, payload.token); } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to log in"); } }
  return <div className="auth-page"><form className="auth-card" onSubmit={submit}><Brand /><small>PLATFORM ADMIN</small><h1>Private control panel</h1><p>This screen is only for Forge operators managing direct-sales gyms.</p><label>Phone number<input required value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} /></label><label>Password<input required type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} /></label>{error && <div className="auth-error">{error}</div>}<button className="primary-btn auth-submit">Log in</button></form></div>;
}

function PlatformCreateGym({ onCreated }: { onCreated: () => void }) {
  const [form, setForm] = useState({ gym_name: "", owner_name: "", owner_phone: "", temporary_password: "", branches: "Main Branch", multi_branch_enabled: false });
  const [error, setError] = useState("");
  async function submit(event: FormEvent) { event.preventDefault(); setError(""); try { await platformApi("/platform/gyms", { method: "POST", body: JSON.stringify({ ...form, branches: form.branches.split(",").map((value) => value.trim()).filter(Boolean) }) }); setForm({ gym_name: "", owner_name: "", owner_phone: "", temporary_password: "", branches: "Main Branch", multi_branch_enabled: false }); onCreated(); } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to create gym"); } }
  return <form className="panel platform-create" onSubmit={submit}><PanelTitle eyebrow="Direct sale setup" title="Create gym credentials" /><div className="form-row"><label>Gym name<input required value={form.gym_name} onChange={(e) => setForm({ ...form, gym_name: e.target.value })} /></label><label>Owner name<input required value={form.owner_name} onChange={(e) => setForm({ ...form, owner_name: e.target.value })} /></label></div><div className="form-row"><label>Owner phone<input required value={form.owner_phone} onChange={(e) => setForm({ ...form, owner_phone: e.target.value })} /></label><label>Temporary password<input required minLength={8} value={form.temporary_password} onChange={(e) => setForm({ ...form, temporary_password: e.target.value })} /></label></div><label>Branches<input required value={form.branches} onChange={(e) => setForm({ ...form, branches: e.target.value })} /><span>Separate multiple branches with commas.</span></label><label className="checkbox-row"><input type="checkbox" checked={form.multi_branch_enabled} onChange={(e) => setForm({ ...form, multi_branch_enabled: e.target.checked })} />Enable paid multi-branch support</label>{error && <div className="auth-error">{error}</div>}<button className="primary-btn">Create credentials</button></form>;
}

function PlatformGymRow({ gym, onChanged }: { gym: PlatformGym; onChanged: () => void }) {
  const owner = gym.owners[0];
  async function setStatus(account_status: "active" | "suspended") { await platformApi(`/platform/gyms/${gym.id}`, { method: "PATCH", body: JSON.stringify({ account_status }) }); onChanged(); }
  async function remove() { if (!confirm(`Delete ${gym.name}? This removes its users, branches, and members.`)) return; await platformApi(`/platform/gyms/${gym.id}`, { method: "DELETE" }); onChanged(); }
  return <div className="platform-row"><div><strong>{gym.name}</strong><small>{gym.workspace_slug} - {gym.branches.length} branch{gym.branches.length === 1 ? "" : "es"}</small></div><div><small>Owner</small><strong>{owner ? `${owner.name} (${owner.phone})` : "No owner"}</strong></div><span className={`status ${gym.account_status === "active" ? "active" : "expired"}`}>{gym.account_status}</span><button className="outline-btn" onClick={() => setStatus(gym.account_status === "active" ? "suspended" : "active")}>{gym.account_status === "active" ? "Suspend" : "Activate"}</button><button className="outline-btn danger" onClick={remove}>Delete</button></div>;
}

function MemberPortal({ view, setView, plan, setPlan, progress, setProgress, showToast, switchPortal }: { view: MemberView; setView: (view: MemberView) => void; plan: Plan; setPlan: (plan: Plan) => void; progress: Progress[]; setProgress: (progress: Progress[]) => void; showToast: (toast: string) => void; switchPortal: () => void }) {
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [showCheckin, setShowCheckin] = useState(false);
  return <div className="member-bg"><div className="mobile-app"><header className="mobile-header"><Brand /><button onClick={switchPortal} title="Owner portal"><Icon name="logout" size={19} /></button></header>
    <main className="mobile-content">
      {view === "home" && <MemberHome plan={plan} progress={progress} openPlan={() => setView("plan")} openOnboarding={() => setShowOnboarding(true)} />}
      {view === "plan" && <PlanView plan={plan} />}
      {view === "progress" && <ProgressView progress={progress} openCheckin={() => setShowCheckin(true)} />}
    </main><nav className="mobile-nav"><button className={view === "home" ? "active" : ""} onClick={() => setView("home")}><Icon name="grid" /><span>Home</span></button><button className={view === "plan" ? "active" : ""} onClick={() => setView("plan")}><Icon name="dumbbell" /><span>My plan</span></button><button className={view === "progress" ? "active" : ""} onClick={() => setView("progress")}><Icon name="chart" /><span>Progress</span></button></nav>
    {showOnboarding && <Onboarding onClose={() => setShowOnboarding(false)} onGenerated={(nextPlan) => { setPlan(nextPlan); setShowOnboarding(false); setView("plan"); showToast("Your new plan is ready"); }} />}
    {showCheckin && <Checkin onClose={() => setShowCheckin(false)} onSaved={(entry) => { setProgress([...progress, entry]); setShowCheckin(false); showToast("Weight check-in saved"); }} />}
  </div></div>;
}
function MemberHome({ plan, progress, openPlan, openOnboarding }: { plan: Plan; progress: Progress[]; openPlan: () => void; openOnboarding: () => void }) { const latest = progress.at(-1)?.weight_kg; const first = progress.at(0)?.weight_kg; return <section><div className="welcome-row"><div><small>GOOD EVENING</small><h1>Aarav, ready to move?</h1></div><div className="member-avatar">AS</div></div><div className="streak-card"><div><small>WEEKLY STREAK</small><strong>3<span>/4</span></strong><p>sessions completed</p></div><div className="ring"><span>75%</span></div></div><div className="section-heading"><div><small>TODAY'S FOCUS</small><h2>Keep the momentum</h2></div><button onClick={openOnboarding}>Reset plan</button></div><button className="workout-card" onClick={openPlan}><div className="workout-icon"><Icon name="dumbbell" /></div><div><small>WORKOUT 03 Â· 48 MIN</small><h3>Upper body + core</h3><p>6 exercises Â· Moderate intensity</p></div><Icon name="arrow" /></button><div className="quick-grid"><div><div className="quick-icon lime"><Icon name="flame" size={17} /></div><small>DAILY TARGET</small><strong>{plan.daily_calories}</strong><p>kcal planned</p></div><div><div className="quick-icon purple"><Icon name="chart" size={17} /></div><small>PROGRESS</small><strong>{latest} kg</strong><p>{first && latest ? `${(first - latest).toFixed(1)} kg down` : "Start logging"}</p></div></div><div className="membership-card"><Icon name="calendar" /><div><small>MEMBERSHIP ACTIVE</small><strong>Strength Annual</strong><p>Renews on 02 Jun 2026</p></div><span>2d</span></div></section>; }
function PlanView({ plan }: { plan: Plan }) { const [tab, setTab] = useState<"workout" | "nutrition">("workout"); return <section><div className="member-page-title"><small>BUILT FOR YOUR GOAL</small><h1>Your {plan.goal_label.toLowerCase()} plan</h1><p>Four weeks of focused, achievable progress.</p></div><div className="plan-summary"><div><Icon name="target" /><small>FOCUS</small><strong>{plan.focus}</strong></div><div><Icon name="flame" /><small>DAILY ENERGY</small><strong>{plan.daily_calories} kcal</strong></div><div><Icon name="dumbbell" /><small>PROTEIN</small><strong>{plan.daily_protein_g}g</strong></div></div><div className="segmented"><button className={tab === "workout" ? "active" : ""} onClick={() => setTab("workout")}>Workout routine</button><button className={tab === "nutrition" ? "active" : ""} onClick={() => setTab("nutrition")}>Diet guide</button></div>{tab === "workout" ? <div className="week-list">{plan.workouts.map((week) => <details key={week.week} open={week.week === 1}><summary><span>0{week.week}</span><div><small>WEEK {week.week}</small><strong>{week.theme}</strong></div><b>+</b></summary><p>{week.target}</p>{week.sessions.map((session, index) => <div className="session" key={session}><span>{index + 1}</span>{session}</div>)}</details>)}</div> : <div className="meal-list"><div className="nutrition-banner"><strong>{plan.water_liters}L water</strong><span>and {plan.daily_protein_g}g protein daily</span></div>{plan.meals.map((meal) => <div className="meal" key={meal.time}><time>{meal.time}</time><div><strong>{meal.name}</strong><p>{meal.detail}</p></div><span>{meal.calories}<small> kcal</small></span></div>)}</div>}<p className="health-note">{plan.note}</p></section>; }
function ProgressView({ progress, openCheckin }: { progress: Progress[]; openCheckin: () => void }) { const latest = progress.at(-1)?.weight_kg ?? 0; const first = progress.at(0)?.weight_kg ?? 0; return <section><div className="member-page-title progress-title"><small>MONTHLY CHECK-IN</small><h1>Your progress</h1><p>Small changes add up. Keep showing up.</p></div><div className="progress-highlight"><div><small>CURRENT WEIGHT</small><strong>{latest}<span> kg</span></strong><p><b>â†“ {(first - latest).toFixed(1)} kg</b> since you started</p></div><button onClick={openCheckin}><Icon name="plus" size={16} />Log weight</button></div><ProgressChart entries={progress} /><div className="checkin-list"><div className="section-heading"><div><small>YOUR HISTORY</small><h2>Monthly check-ins</h2></div></div>{[...progress].reverse().map((entry, index) => <div className="checkin" key={entry.id}><div><strong>{formatDate(entry.recorded_on)}</strong><small>{index === 0 ? "Latest check-in" : "Recorded weight"}</small></div><b>{entry.weight_kg}<span> kg</span></b></div>)}</div></section>; }
function ProgressChart({ entries }: { entries: Progress[] }) { const values = entries.map((entry) => entry.weight_kg); const min = Math.min(...values) - 1; const max = Math.max(...values) + 1; const points = entries.map((entry, index) => `${26 + index * (260 / Math.max(entries.length - 1, 1))},${25 + ((max - entry.weight_kg) / (max - min)) * 120}`).join(" "); return <div className="chart-card"><div className="chart-head"><small>WEIGHT TREND</small><span>LAST 4 MONTHS</span></div><svg viewBox="0 0 312 180"><path d="M20 35H300M20 85H300M20 135H300" className="grid-lines" /><polyline points={points} className="chart-line" />{entries.map((entry, index) => { const [x, y] = points.split(" ")[index].split(","); return <circle key={entry.id} cx={x} cy={y} r="4" className="chart-point" />; })}</svg></div>; }
function Onboarding({ onClose, onGenerated }: { onClose: () => void; onGenerated: (plan: Plan) => void }) { const [step, setStep] = useState(1); const [form, setForm] = useState({ weight_kg: 77.8, height_cm: 178, age: 28, goal: "get-lean" as Goal }); async function generate() { let result = fallbackPlan; try { result = await api<Plan>("/plans/generate", { method: "POST", body: JSON.stringify({ member_id: 1, ...form }) }); } catch { /* demo */ } onGenerated(result); } return <div className="member-modal"><button className="modal-close" onClick={onClose}>Ã—</button><div className="onboard-progress"><i className="active" /><i className={step === 2 ? "active" : ""} /></div>{step === 1 ? <div><small>STEP 1 OF 2</small><h2>Let's set your baseline.</h2><p>This helps us tailor your starting plan.</p><div className="metric-inputs"><label><span>Weight</span><div><input type="number" value={form.weight_kg} onChange={(e) => setForm({ ...form, weight_kg: Number(e.target.value) })} /><b>kg</b></div></label><label><span>Height</span><div><input type="number" value={form.height_cm} onChange={(e) => setForm({ ...form, height_cm: Number(e.target.value) })} /><b>cm</b></div></label><label><span>Age</span><div><input type="number" value={form.age} onChange={(e) => setForm({ ...form, age: Number(e.target.value) })} /><b>yrs</b></div></label></div><button className="member-cta" onClick={() => setStep(2)}>Continue <Icon name="arrow" size={16} /></button></div> : <div><small>STEP 2 OF 2</small><h2>What are we working toward?</h2><p>Choose your primary goal for the next four weeks.</p><div className="goal-list">{([["lose-weight", "Lose weight", "Reduce body fat steadily"], ["build-muscle", "Build muscle", "Increase strength and size"], ["get-lean", "Get lean", "Improve definition and fitness"]] as const).map(([value, title, copy]) => <button className={form.goal === value ? "active" : ""} onClick={() => setForm({ ...form, goal: value })} key={value}><Icon name={value === "build-muscle" ? "dumbbell" : value === "get-lean" ? "flame" : "target"} /><div><strong>{title}</strong><span>{copy}</span></div></button>)}</div><button className="member-cta" onClick={generate}>Generate my plan <Icon name="arrow" size={16} /></button></div>}</div>; }
function Checkin({ onClose, onSaved }: { onClose: () => void; onSaved: (entry: Progress) => void }) { const [weight, setWeight] = useState(77.3); async function save() { const body = { weight_kg: weight, recorded_on: new Date().toISOString().slice(0, 10) }; let entry = { id: Date.now(), ...body }; try { entry = await api<Progress>("/progress/1", { method: "POST", body: JSON.stringify(body) }); } catch { /* demo */ } onSaved(entry); } return <div className="member-modal checkin-modal"><button className="modal-close" onClick={onClose}>Ã—</button><small>MONTHLY CHECK-IN</small><h2>Log your weight</h2><p>Consistency matters more than any single number.</p><label className="weight-entry"><input autoFocus type="number" step="0.1" value={weight} onChange={(e) => setWeight(Number(e.target.value))} /><b>kg</b></label><button className="member-cta" onClick={save}>Save check-in <Icon name="arrow" size={16} /></button></div>; }
