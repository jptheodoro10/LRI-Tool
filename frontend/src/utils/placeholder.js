const phase1PlaceholdersInOrder = [
  'Ex: Many Machine Learning (ML) projects are developed by data scientists from diverse backgrounds without a solid foundation in software design principles, making it difficult to understand and maintain the ML code in the long term...',
  'Ex: In the context of industrial ML code, the experimental and iterative nature of ML model development encourages rapid coding practices, often neglecting software design principles...',
  'Ex: Poorly designed ML projects suffer from maintenance and sustainability problems, leading to increased costs, low productivity and difficulty in scaling and evolving systems...',
  'Ex: Data scientist involved in maintaining ML systems...',
  'Ex: Aho et al. Demystifying data science projects: A look on the people and process of data science today. PROFES 2020...',
  'Ex: Analyze the <application of SOLID design principles> for the purpose of <characterization> with respect to their <impact on ML code understanding> from the point of view of <data scientists> in the context of <industrial ML code>...',
  'Ex: List the key research questions your study must answer. Example: How does this approach affect code understanding? What benefits are perceived by practitioners?',
];

const phase1FieldOrder = [
  'Describe the pain point',
  'Characterize the environment',
  'Consequences/Benefits',
  'Identify People Involved',
  'What scientific evidence?',
  'Define the objectives',
  'What research questions?',
];

export function getFieldPlaceholder(field) {
  const idx = phase1FieldOrder.indexOf(field);
  if (idx >= 0) return phase1PlaceholdersInOrder[idx];
  return `Write ${String(field || '').replaceAll('_', ' ')}...`;
}
