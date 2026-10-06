import { useState } from 'react'
import { Brain, ChevronDown, Pencil, X } from 'lucide-react'
import type { Fact, Profile } from '../api'
import { capitalize, FACT_TYPE_LABELS, factWhen, formatDate, ZODIAC_GLYPHS } from
'../format'
interface Props {
 open: boolean
 profile: Profile | null
 facts: Fact[]
 onEditProfile: () => void
 onClose: () => void
}

const TYPE_ORDER: Fact['type'][] = ['goal', 'interest', 'preference', 'memory']
export function BrainPanel({ open, profile, facts, onEditProfile, onClose }: Props) {
 const [showHistory, setShowHistory] = useState(false)
 const active = facts.filter((f) => f.status === 'active')
 const past = facts.filter((f) => f.status !== 'active')
 const labelById = new Map(facts.map((f) => [f.id, f.label]))
 return (
 <aside className={open ? 'panel panel-right open' : 'panel panel-right'} aria-label="Shared Brain">
 <div className="panel-header">
 <h2 className="panel-title"><Brain size={18} /> Shared Brain</h2>
 <button type="button" className="icon-button drawer-close-right" aria-label="Close
Shared Brain" onClick={onClose}>
 <X size={18} />
 </button>
 </div>
 <section className="card profile-card" aria-labelledby="profile-heading">
 <div className="card-header">
 <h3 id="profile-heading">Profile</h3>
 <button type="button" className="icon-button small" aria-label="Edit profile"
onClick={onEditProfile}>
 <Pencil size={15} />
 </button>
 </div>
 {profile?.zodiac_sign && (
 <div className="sign">
 <span className="sign-glyph" aria-hidden="true">
{ZODIAC_GLYPHS[profile.zodiac_sign]}</span>
 <div>
 <span className="sign-name">{profile.zodiac_sign}</span>
 <span className="muted small">Sun sign</span>
 </div>
 </div>
 )}
 <dl className="profile-list">
 <ProfileRow label="Name" value={profile?.name} />
 <ProfileRow label="Born" value={formatDate(profile?.dob ?? null)} />
 <ProfileRow label="Time" value={profile?.time_of_birth} />
 <ProfileRow label="Place" value={profile?.birth_place} />
 <ProfileRow label="Language" value={profile?.preferred_language} />
 </dl>
 {!profile?.dob && (
 <button type="button" className="link-button small" onClick={onEditProfile}>
 Add your birth date to see your sun sign
 </button>
 )}
 </section>
 {active.length === 0 && (
 <p className="muted small empty-note">
 Nothing remembered yet. Tell me about a goal, interest or preference and it will
appear here.
 </p>
 )}
 {TYPE_ORDER.map((type) => {
 const group = active.filter((f) => f.type === type)
 if (group.length === 0) return null
 return (
 <section key={type} className="card" aria-label={FACT_TYPE_LABELS[type]}>
 <h3>{FACT_TYPE_LABELS[type]}</h3>
 <ul className="fact-list">
 {group.map((fact) => (
 <li key={fact.id} className="fact">
 <span className="fact-label">{capitalize(fact.label)}</span>
 <div className="fact-meta">
 {fact.life_area && <span className={`pill area-${fact.life_area}`}>
{capitalize(fact.life_area)}</span>}
 {factWhen(fact) && <span className="pill">{factWhen(fact)}</span>}
 <span
 className="confidence"
role="meter"
aria-label="Confidence"
aria-valuemin={0}
aria-valuemax={100}
aria-valuenow={Math.round(fact.confidence * 100)}
title={`Confidence ${Math.round(fact.confidence * 100)}%`}
 >
 <span style={{ width: `${fact.confidence * 100}%` }} />
 </span>
 </div>
 {fact.supersedes_id && (
 <span className="muted small">Replaced
“{labelById.get(fact.supersedes_id) ?? 'an earlier fact'}”</span>
 )}
 </li>
 ))}
 </ul>
 </section>
 )
 })}
 {past.length > 0 && (
 <section className="card">
 <button type="button" className="history-toggle" aria-expanded={showHistory}
onClick={() => setShowHistory((s) => !s)}>
 <span>Change history ({past.length})</span>
 <ChevronDown size={16} className={showHistory ? 'chevron open' : 'chevron'} />
 </button>
 {showHistory && (
 <ul className="fact-list past">
 {past.map((fact) => (
 <li key={fact.id} className="fact">
 <span className="fact-label">{capitalize(fact.label)}</span>
 <span className="muted small">{fact.status === 'superseded' ? 'Replaced'
: 'Removed'}</span>
 </li>
 ))}
 </ul>
 )}
 </section>
 )}
 </aside>
 )
}
function ProfileRow({ label, value }: { label: string; value: string | null | undefined })
{
 return (
 <div className="profile-row">
 <dt>{label}</dt>
 <dd className={value ? undefined : 'muted'}>{value || 'Not set'}</dd>
 </div>
 )
}