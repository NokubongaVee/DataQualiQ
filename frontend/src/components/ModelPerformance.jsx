import { percentage } from '../utils/intrusionResults'

export default function ModelPerformance({ intrusion }) {
  const metrics = intrusion.data?.metrics
  const values = [['Accuracy', 'accuracy'], ['Precision', 'precision'], ['Recall', 'recall'], ['F1 score', 'f1']]
  return <section className="panel middle-panel">
    <h2>Model performance</h2><div className="model-grid">{values.map(([label, key]) => <div key={key}><span>{label}</span><strong>{percentage(metrics?.[key])}</strong></div>)}</div>
    <p className="panel-note">{values.every(([, key]) => percentage(metrics?.[key]) === 'Pending') ? 'Model performance metrics will appear after the intrusion-detection model is connected.' : 'Evaluation metrics supplied by the model. They describe model performance, not individual record reliability.'}</p>
  </section>
}
