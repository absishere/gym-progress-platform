import { FormEvent, ReactElement, useEffect, useState } from "react";
import "./styles.css";

const API_URL = "http://127.0.0.1:8000/api";
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
  const response = await fetch(`${API_URL}${path}`, { headers: { "Content-Type": "application/json" }, ...options });
  if (!response.ok) throw new Error("API request failed");
  return response.json();
}
function initials(name: string) { return name.split(" ").map((word) => word[0]).join("").slice(0, 2); }
function formatDate(value: string) { return new Intl.DateTimeFormat("en", { day: "numeric", month: "short" }).format(new Date(`${value}T00:00:00`)); }

export default function App() {
  const [portal, setPortal] = useState<Portal>("owner");
  const [ownerView, setOwnerView] = useState<OwnerView>("overview");
  const [memberView, setMemberView] = useState<MemberView>("home");
  const [members, setMembers] = useState<Member[]>(fallbackMembers);
  const [plan, setPlan] = useState<Plan>(fallbackPlan);
  const [progress, setProgress] = useState<Progress[]>(fallbackProgress);
  const [toast, setToast] = useState("");
  useEffect(() => { api<Member[]>("/members").then(setMembers).catch(() => undefined); api<Plan>("/plans/1").then(setPlan).catch(() => undefined); api<Progress[]>("/progress/1").then(setProgress).catch(() => undefined); }, []);
  useEffect(() => { if (!toast) return; const timeout = setTimeout(() => setToast(""), 2600); return () => clearTimeout(timeout); }, [toast]);
  return <div className="app-shell">
    {toast && <div className="toast"><span>✓</span>{toast}</div>}
    {portal === "owner"
      ? <OwnerPortal members={members} setMembers={setMembers} view={ownerView} setView={setOwnerView} showToast={setToast} switchPortal={() => setPortal("member")} />
      : <MemberPortal view={memberView} setView={setMemberView} plan={plan} setPlan={setPlan} progress={progress} setProgress={setProgress} showToast={setToast} switchPortal={() => setPortal("owner")} />}
  </div>;
}

function Brand() { return <div className="brand"><div className="brand-mark">F</div><div><strong>FORGE</strong><span>PERFORMANCE CLUB</span></div></div>; }
function OwnerPortal({ members, setMembers, view, setView, showToast, switchPortal }: { members: Member[]; setMembers: (members: Member[]) => void; view: OwnerView; setView: (view: OwnerView) => void; showToast: (toast: string) => void; switchPortal: () => void }) {
  const [showAdd, setShowAdd] = useState(false);
  const expiring = members.filter((member) => member.days_left >= 0 && member.days_left <= 7);
  const active = members.filter((member) => member.status !== "expired").length;
  async function refresh() { try { setMembers(await api<Member[]>("/members")); } catch { /* local preview keeps fallback state */ } }
  async function remind(id?: number) {
    try { await api(id ? `/reminders/${id}` : "/reminders/expiring", { method: "POST" }); } catch { /* demo mode */ }
    showToast(id ? "WhatsApp reminder queued" : `${expiring.length} WhatsApp reminders queued`);
  }
  return <div className="owner-layout">
    <aside className="sidebar">
      <Brand />
      <nav>
        <button className={view === "overview" ? "active" : ""} onClick={() => setView("overview")}><Icon name="grid" />Overview</button>
        <button className={view === "members" ? "active" : ""} onClick={() => setView("members")}><Icon name="users" />Members<span>{members.length}</span></button>
        <button className={view === "retention" ? "active" : ""} onClick={() => setView("retention")}><Icon name="bell" />Retention<span className="alert-count">{expiring.length}</span></button>
      </nav>
      <div className="sidebar-bottom">
        <button onClick={switchPortal}><Icon name="arrow" />Member preview</button>
        <div className="owner-profile"><div className="avatar">AK</div><div><strong>Arjun Khanna</strong><small>Gym owner</small></div></div>
      </div>
    </aside>
    <main className="owner-main">
      <header className="topbar"><div><small>Sunday, 31 May</small><h1>{view === "overview" ? "Good evening, Arjun" : view === "members" ? "Member directory" : "Retention center"}</h1></div><button className="primary-btn" onClick={() => setShowAdd(true)}><Icon name="plus" size={16} />Add member</button></header>
      {view === "overview" && <OwnerOverview members={members} active={active} expiring={expiring} remind={remind} setView={setView} />}
      {view === "members" && <MemberDirectory members={members} remind={remind} />}
      {view === "retention" && <Retention members={expiring} remind={remind} />}
    </main>
    {showAdd && <AddMember onClose={() => setShowAdd(false)} onSaved={() => { refresh(); setShowAdd(false); showToast("Member added successfully"); }} />}
  </div>;
}
function OwnerOverview({ members, active, expiring, remind, setView }: { members: Member[]; active: number; expiring: Member[]; remind: (id?: number) => void; setView: (view: OwnerView) => void }) {
  const recent = members.slice(0, 4);
  return <section>
    <div className="metric-grid">
      <Metric label="Active members" value={active.toString()} change="+12% this month" icon="users" tone="lime" />
      <Metric label="Expiring this week" value={expiring.length.toString()} change="Needs attention" icon="bell" tone="amber" />
      <Metric label="Renewal rate" value="84%" change="+6% vs last month" icon="chart" tone="purple" />
      <Metric label="Monthly revenue" value="₹2.48L" change="+18% this month" icon="flame" tone="blue" />
    </div>
    <div className="dashboard-grid">
      <div className="panel expiring-panel"><PanelTitle eyebrow="Retention radar" title="Expiring this week" action="View all" onClick={() => setView("retention")} /><p className="panel-copy">Reach out before these memberships lapse.</p><div className="compact-list">{expiring.map((member) => <CompactMember key={member.id} member={member} remind={remind} />)}</div></div>
      <div className="panel insight-panel"><div className="insight-top"><span className="pulse-dot" /><small>LIVE INSIGHT</small></div><h2>3 renewals can protect <em>₹18,500</em> in monthly value.</h2><p>Send a quick WhatsApp nudge while your members are still active.</p><button className="dark-btn" onClick={() => remind()}><Icon name="whatsapp" size={17} />Send all reminders</button></div>
    </div>
    <div className="panel recent-panel"><PanelTitle eyebrow="Member base" title="Recent memberships" action="Open directory" onClick={() => setView("members")} /><MemberTable members={recent} remind={remind} /></div>
  </section>;
}
function Metric({ label, value, change, icon, tone }: { label: string; value: string; change: string; icon: string; tone: string }) { return <div className="metric-card"><div className={`metric-icon ${tone}`}><Icon name={icon} /></div><div><small>{label}</small><strong>{value}</strong><span>{change}</span></div></div>; }
function PanelTitle({ eyebrow, title, action, onClick }: { eyebrow: string; title: string; action?: string; onClick?: () => void }) { return <div className="panel-title"><div><small>{eyebrow}</small><h2>{title}</h2></div>{action && <button onClick={onClick}>{action}<Icon name="arrow" size={15} /></button>}</div>; }
function CompactMember({ member, remind }: { member: Member; remind: (id?: number) => void }) { return <div className="compact-member"><div className="avatar soft">{initials(member.name)}</div><div><strong>{member.name}</strong><small>{member.package}</small></div><div className="expiry"><b>{member.days_left}d</b><small>left</small></div><button onClick={() => remind(member.id)}><Icon name="whatsapp" size={17} /></button></div>; }
function MemberDirectory({ members, remind }: { members: Member[]; remind: (id: number) => void }) { const [search, setSearch] = useState(""); const filtered = members.filter((member) => member.name.toLowerCase().includes(search.toLowerCase())); return <section className="panel table-page"><div className="directory-head"><PanelTitle eyebrow="All records" title="Member directory" /><label className="search">⌕<input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search member" /></label></div><MemberTable members={filtered} remind={remind} /></section>; }
function MemberTable({ members, remind }: { members: Member[]; remind: (id: number) => void }) { return <div className="table-wrap"><table><thead><tr><th>Member</th><th>Package</th><th>Expiry</th><th>Status</th><th></th></tr></thead><tbody>{members.map((member) => <tr key={member.id}><td><div className="member-cell"><div className="avatar soft">{initials(member.name)}</div><div><strong>{member.name}</strong><small>{member.phone}</small></div></div></td><td>{member.package}</td><td>{formatDate(member.expires_on)}</td><td><span className={`status ${member.status}`}>{member.status}</span></td><td><button className="icon-btn" onClick={() => remind(member.id)}><Icon name="whatsapp" size={17} /></button></td></tr>)}</tbody></table></div>; }
function Retention({ members, remind }: { members: Member[]; remind: (id?: number) => void }) { return <section><div className="retention-hero"><div><small>WEEKLY RETENTION QUEUE</small><h2>Stay ahead of every expiry.</h2><p>{members.length} members are due for a thoughtful check-in this week.</p></div><button className="dark-btn" onClick={() => remind()}><Icon name="whatsapp" size={17} />Send all reminders</button></div><div className="panel"><PanelTitle eyebrow="Next 7 days" title="Members to contact" /><div className="retention-list">{members.map((member) => <div className="retention-row" key={member.id}><div className="avatar soft">{initials(member.name)}</div><div className="retention-name"><strong>{member.name}</strong><small>{member.phone}</small></div><div><small>Package</small><strong>{member.package}</strong></div><div><small>Expires</small><strong>{formatDate(member.expires_on)} · {member.days_left} days</strong></div><button className="outline-btn" onClick={() => remind(member.id)}><Icon name="whatsapp" size={16} />Remind</button></div>)}</div></div></section>; }
function AddMember({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const [form, setForm] = useState({ name: "", phone: "", email: "", package: "Transform 3 Month", expires_on: "2026-06-30" });
  async function submit(event: FormEvent) { event.preventDefault(); try { await api("/members", { method: "POST", body: JSON.stringify(form) }); } catch { /* preview submits without API */ } onSaved(); }
  return <div className="modal-backdrop"><form className="modal" onSubmit={submit}><button type="button" className="modal-close" onClick={onClose}>×</button><small>NEW MEMBERSHIP</small><h2>Add a member</h2><p>Create their membership record and track the renewal date.</p><label>Full name<input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="e.g. Neha Rao" /></label><label>WhatsApp number<input required value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} placeholder="+91 98765 43210" /></label><label>Email<input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} placeholder="member@example.com" /></label><div className="form-row"><label>Package<select value={form.package} onChange={(e) => setForm({ ...form, package: e.target.value })}><option>Transform 3 Month</option><option>Strength Annual</option><option>Open Gym Monthly</option></select></label><label>Expires on<input required type="date" value={form.expires_on} onChange={(e) => setForm({ ...form, expires_on: e.target.value })} /></label></div><button className="primary-btn modal-submit">Add membership</button></form></div>;
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
function MemberHome({ plan, progress, openPlan, openOnboarding }: { plan: Plan; progress: Progress[]; openPlan: () => void; openOnboarding: () => void }) { const latest = progress.at(-1)?.weight_kg; const first = progress.at(0)?.weight_kg; return <section><div className="welcome-row"><div><small>GOOD EVENING</small><h1>Aarav, ready to move?</h1></div><div className="member-avatar">AS</div></div><div className="streak-card"><div><small>WEEKLY STREAK</small><strong>3<span>/4</span></strong><p>sessions completed</p></div><div className="ring"><span>75%</span></div></div><div className="section-heading"><div><small>TODAY'S FOCUS</small><h2>Keep the momentum</h2></div><button onClick={openOnboarding}>Reset plan</button></div><button className="workout-card" onClick={openPlan}><div className="workout-icon"><Icon name="dumbbell" /></div><div><small>WORKOUT 03 · 48 MIN</small><h3>Upper body + core</h3><p>6 exercises · Moderate intensity</p></div><Icon name="arrow" /></button><div className="quick-grid"><div><div className="quick-icon lime"><Icon name="flame" size={17} /></div><small>DAILY TARGET</small><strong>{plan.daily_calories}</strong><p>kcal planned</p></div><div><div className="quick-icon purple"><Icon name="chart" size={17} /></div><small>PROGRESS</small><strong>{latest} kg</strong><p>{first && latest ? `${(first - latest).toFixed(1)} kg down` : "Start logging"}</p></div></div><div className="membership-card"><Icon name="calendar" /><div><small>MEMBERSHIP ACTIVE</small><strong>Strength Annual</strong><p>Renews on 02 Jun 2026</p></div><span>2d</span></div></section>; }
function PlanView({ plan }: { plan: Plan }) { const [tab, setTab] = useState<"workout" | "nutrition">("workout"); return <section><div className="member-page-title"><small>BUILT FOR YOUR GOAL</small><h1>Your {plan.goal_label.toLowerCase()} plan</h1><p>Four weeks of focused, achievable progress.</p></div><div className="plan-summary"><div><Icon name="target" /><small>FOCUS</small><strong>{plan.focus}</strong></div><div><Icon name="flame" /><small>DAILY ENERGY</small><strong>{plan.daily_calories} kcal</strong></div><div><Icon name="dumbbell" /><small>PROTEIN</small><strong>{plan.daily_protein_g}g</strong></div></div><div className="segmented"><button className={tab === "workout" ? "active" : ""} onClick={() => setTab("workout")}>Workout routine</button><button className={tab === "nutrition" ? "active" : ""} onClick={() => setTab("nutrition")}>Diet guide</button></div>{tab === "workout" ? <div className="week-list">{plan.workouts.map((week) => <details key={week.week} open={week.week === 1}><summary><span>0{week.week}</span><div><small>WEEK {week.week}</small><strong>{week.theme}</strong></div><b>+</b></summary><p>{week.target}</p>{week.sessions.map((session, index) => <div className="session" key={session}><span>{index + 1}</span>{session}</div>)}</details>)}</div> : <div className="meal-list"><div className="nutrition-banner"><strong>{plan.water_liters}L water</strong><span>and {plan.daily_protein_g}g protein daily</span></div>{plan.meals.map((meal) => <div className="meal" key={meal.time}><time>{meal.time}</time><div><strong>{meal.name}</strong><p>{meal.detail}</p></div><span>{meal.calories}<small> kcal</small></span></div>)}</div>}<p className="health-note">{plan.note}</p></section>; }
function ProgressView({ progress, openCheckin }: { progress: Progress[]; openCheckin: () => void }) { const latest = progress.at(-1)?.weight_kg ?? 0; const first = progress.at(0)?.weight_kg ?? 0; return <section><div className="member-page-title progress-title"><small>MONTHLY CHECK-IN</small><h1>Your progress</h1><p>Small changes add up. Keep showing up.</p></div><div className="progress-highlight"><div><small>CURRENT WEIGHT</small><strong>{latest}<span> kg</span></strong><p><b>↓ {(first - latest).toFixed(1)} kg</b> since you started</p></div><button onClick={openCheckin}><Icon name="plus" size={16} />Log weight</button></div><ProgressChart entries={progress} /><div className="checkin-list"><div className="section-heading"><div><small>YOUR HISTORY</small><h2>Monthly check-ins</h2></div></div>{[...progress].reverse().map((entry, index) => <div className="checkin" key={entry.id}><div><strong>{formatDate(entry.recorded_on)}</strong><small>{index === 0 ? "Latest check-in" : "Recorded weight"}</small></div><b>{entry.weight_kg}<span> kg</span></b></div>)}</div></section>; }
function ProgressChart({ entries }: { entries: Progress[] }) { const values = entries.map((entry) => entry.weight_kg); const min = Math.min(...values) - 1; const max = Math.max(...values) + 1; const points = entries.map((entry, index) => `${26 + index * (260 / Math.max(entries.length - 1, 1))},${25 + ((max - entry.weight_kg) / (max - min)) * 120}`).join(" "); return <div className="chart-card"><div className="chart-head"><small>WEIGHT TREND</small><span>LAST 4 MONTHS</span></div><svg viewBox="0 0 312 180"><path d="M20 35H300M20 85H300M20 135H300" className="grid-lines" /><polyline points={points} className="chart-line" />{entries.map((entry, index) => { const [x, y] = points.split(" ")[index].split(","); return <circle key={entry.id} cx={x} cy={y} r="4" className="chart-point" />; })}</svg></div>; }
function Onboarding({ onClose, onGenerated }: { onClose: () => void; onGenerated: (plan: Plan) => void }) { const [step, setStep] = useState(1); const [form, setForm] = useState({ weight_kg: 77.8, height_cm: 178, age: 28, goal: "get-lean" as Goal }); async function generate() { let result = fallbackPlan; try { result = await api<Plan>("/plans/generate", { method: "POST", body: JSON.stringify({ member_id: 1, ...form }) }); } catch { /* demo */ } onGenerated(result); } return <div className="member-modal"><button className="modal-close" onClick={onClose}>×</button><div className="onboard-progress"><i className="active" /><i className={step === 2 ? "active" : ""} /></div>{step === 1 ? <div><small>STEP 1 OF 2</small><h2>Let's set your baseline.</h2><p>This helps us tailor your starting plan.</p><div className="metric-inputs"><label><span>Weight</span><div><input type="number" value={form.weight_kg} onChange={(e) => setForm({ ...form, weight_kg: Number(e.target.value) })} /><b>kg</b></div></label><label><span>Height</span><div><input type="number" value={form.height_cm} onChange={(e) => setForm({ ...form, height_cm: Number(e.target.value) })} /><b>cm</b></div></label><label><span>Age</span><div><input type="number" value={form.age} onChange={(e) => setForm({ ...form, age: Number(e.target.value) })} /><b>yrs</b></div></label></div><button className="member-cta" onClick={() => setStep(2)}>Continue <Icon name="arrow" size={16} /></button></div> : <div><small>STEP 2 OF 2</small><h2>What are we working toward?</h2><p>Choose your primary goal for the next four weeks.</p><div className="goal-list">{([["lose-weight", "Lose weight", "Reduce body fat steadily"], ["build-muscle", "Build muscle", "Increase strength and size"], ["get-lean", "Get lean", "Improve definition and fitness"]] as const).map(([value, title, copy]) => <button className={form.goal === value ? "active" : ""} onClick={() => setForm({ ...form, goal: value })} key={value}><Icon name={value === "build-muscle" ? "dumbbell" : value === "get-lean" ? "flame" : "target"} /><div><strong>{title}</strong><span>{copy}</span></div></button>)}</div><button className="member-cta" onClick={generate}>Generate my plan <Icon name="arrow" size={16} /></button></div>}</div>; }
function Checkin({ onClose, onSaved }: { onClose: () => void; onSaved: (entry: Progress) => void }) { const [weight, setWeight] = useState(77.3); async function save() { const body = { weight_kg: weight, recorded_on: new Date().toISOString().slice(0, 10) }; let entry = { id: Date.now(), ...body }; try { entry = await api<Progress>("/progress/1", { method: "POST", body: JSON.stringify(body) }); } catch { /* demo */ } onSaved(entry); } return <div className="member-modal checkin-modal"><button className="modal-close" onClick={onClose}>×</button><small>MONTHLY CHECK-IN</small><h2>Log your weight</h2><p>Consistency matters more than any single number.</p><label className="weight-entry"><input autoFocus type="number" step="0.1" value={weight} onChange={(e) => setWeight(Number(e.target.value))} /><b>kg</b></label><button className="member-cta" onClick={save}>Save check-in <Icon name="arrow" size={16} /></button></div>; }
