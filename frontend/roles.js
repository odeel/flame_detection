// KPI values are MOCK placeholders; replace with real PSI numbers when the data layer exists.
export const ROLES = {
  researcher: {
    label: 'Researcher', canViewAs: 'engineer',
    headline: ['Turn NASA combustion research into mission-ready', 'fire intelligence.'],
    search: 'Search investigations, fuels, variables…',
    queries: ['Which tests cover lunar base conditions?', 'Is there partial-gravity data?', 'How is fire suppressed in a spacecraft?'],
    title: 'PSI investigation explorer', options: ['Explorer', 'Compare', 'Modeling data'], habitats: true,
    kpis: [['12 TB', 'Combustion data'], ['20', 'Investigations'], ['85%', 'Highest O₂ tested'], ['0', 'Partial-gravity datasets']],
  },
  engineer: {
    label: 'Engineer', canViewAs: 'researcher',
    headline: ['Choose fire-safety controls for your habitat with', 'fire intelligence.'],
    search: 'Search controls, materials, habitats…',
    queries: ['Which materials are riskiest at 30% O₂?', 'How is smoke detected in microgravity?', 'Which agents suppress fire best?'],
    title: 'Fire safety controls', options: ['Fire controls', 'Habitats', 'Explorer'], habitats: true,
    kpis: [['3', 'Habitat atmospheres'], ['3', 'Safety pillars'], ['30%+', 'Expected lunar O₂'], ['≤10.2 psi', 'Expected lunar pressure']],
  },
  student: {
    label: 'Student', canViewAs: null,
    headline: ['Learn how fire behaves in space and protects us on', 'Earth.'],
    search: 'Ask anything about fire in space…',
    queries: ['Why is a flame round in space?', 'How do astronauts stay safe from fire?', 'How does space research help firefighters?'],
    title: 'Earth impact explorer', options: ['Earth impact', 'Fire basics', 'Ask AI'], habitats: false,
    kpis: [['4', 'Earth technologies'], ['3', 'Safety pillars'], ['0 g', 'Why flames turn round']],
  },
};
