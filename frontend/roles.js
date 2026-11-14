export const ROLES = {
  researcher: {
    label: 'Researcher', canViewAs: 'engineer',
    headline: ['Turn NASA combustion research into mission-ready', 'fire intelligence.'],
    search: 'Ask about flammability, extinction, test conditions…',
    queries: ['Which tests cover lunar base conditions?', 'Is there partial-gravity data?', 'How is fire suppressed in a spacecraft?'],
    title: 'PSI investigation explorer', options: ['Explorer', 'Compare', 'Habitats', 'Modeling data'], habitats: true,
  },
  engineer: {
    label: 'Engineer', canViewAs: 'researcher',
    headline: ['Choose fire-safety controls for your habitat with', 'fire intelligence.'],
    search: 'Ask about materials, smoke detection, suppression…',
    queries: ['Which materials are riskiest in elevated oxygen?', 'How is smoke detected in microgravity?', 'Which agents suppress fire best?'],
    title: 'Fire safety explorer', options: ['Explorer', 'Habitats', 'Compare'], habitats: true,
  },
  student: {
    label: 'Student', canViewAs: null,
    headline: ['Learn how fire behaves in space and protects us on', 'Earth.'],
    search: 'Ask anything about fire in space…',
    queries: ['Why is a flame round in space?', 'How do astronauts stay safe from fire?', 'How does space research help firefighters?'],
    title: 'Earth impact explorer', options: ['Earth impact', 'Fire basics', 'Ask AI'], habitats: false,
  },
};
