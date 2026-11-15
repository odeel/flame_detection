// Per-role configuration. `sections` are panel ids rendered in order by homepage.jsx (see PANELS in sections.jsx).
// `library` lists the tabs of the investigation library card. Add a panel: create it in sections.jsx and list its id here.
export const ROLES = {
  researcher: {
    label: 'Researcher', icon: 'beaker', workspace: 'Research lab', canViewAs: 'engineer',
    blurb: 'Full predictive model, flammability maps, test-gap finder, material risk analysis and the complete PSI data.',
    headline: ['Turn NASA combustion research into mission-ready', 'fire intelligence.'],
    lead: 'Run the droplet-flame model, map where flames sustain themselves, and find the conditions NASA has not tested yet.',
    search: 'Search NASA combustion data (e.g. "Show solid material extinction limits in 30% O₂")',
    queries: ['Which tests cover lunar base conditions?', 'Is there partial-gravity data?', 'Extinction limits in elevated O₂', 'Which fuels were tested with both CO₂ and helium?'],
    habitats: true,
    sections: ['simulator', 'gaps', 'materials', 'library', 'lessons'],
    library: ['Explorer', 'Compare', 'Habitats', 'Partial gravity'],
  },
  engineer: {
    label: 'Engineer', icon: 'wrench', workspace: 'Habitat safety', canViewAs: 'researcher',
    blurb: 'Fire controls, what-if scenarios and flammability maps to choose safety measures for a habitat.',
    headline: ['Choose fire-safety controls for your habitat with', 'fire intelligence.'],
    lead: 'See which NASA studies back each safety pillar, then test how changing the cabin atmosphere changes fire risk.',
    search: 'Ask about materials, smoke detection, suppression…',
    queries: ['Which materials are riskiest in elevated oxygen?', 'How is smoke detected in microgravity?', 'Which agents suppress fire best?', 'Fire risks in ISS'],
    habitats: true,
    sections: ['controls', 'scenario', 'library', 'lessons'],
    library: ['Explorer', 'Compare', 'Habitats', 'Partial gravity'],
  },
  student: {
    label: 'Student', icon: 'grad', workspace: 'Learn', canViewAs: null,
    blurb: 'A friendly flame playground, fire basics, and how space research protects people on Earth.',
    headline: ['Learn how fire behaves in space and protects us on', 'Earth.'],
    lead: 'Play with a real NASA flame model, see why flames turn round in space, and discover the space technology firefighters use today.',
    search: 'Ask anything about fire in space…',
    queries: ['Why is a flame round in space?', 'How do astronauts stay safe from fire?', 'How does space research help firefighters?'],
    habitats: false,
    sections: ['playground', 'basics', 'earth', 'globe', 'lessons', 'askai'],
    library: [],
  },
};
