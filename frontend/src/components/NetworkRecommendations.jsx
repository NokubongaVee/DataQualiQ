export default function NetworkRecommendations({ recommendations }) {
  const renderItem = (item, index) => <li key={index}><span className={`network-priority priority-${item.priority}`}>{item.priority} priority</span><strong>{item.message}</strong><p>{item.reason}</p>{item.affected_records != null && <small>{item.affected_records.toLocaleString()} affected records</small>}</li>
  return <aside className="panel recommendations-panel"><h2>Security recommendations</h2>
    <p className="panel-note">Decision support for human review and investigation.</p>
    {recommendations.length ? <><ul className="network-recommendations">{recommendations.slice(0, 3).map(renderItem)}</ul>{recommendations.length > 3 && <details className="remaining-recommendations"><summary>View {recommendations.length - 3} more recommendations</summary><ul className="network-recommendations">{recommendations.slice(3).map(renderItem)}</ul></details>}</> : <p className="panel-note">No recommendations were returned by the backend.</p>}
  </aside>
}
