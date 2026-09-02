

export const showsRawDataTab = (category) => category !== 'Master Experiment'


export const showsNatureOfSample = (category) =>
  ['Sub Experiment', 'Experiment'].includes(category)


export const showsQualityMetrics = (natureOfSample) => Boolean(natureOfSample)


export const showsSubMetrics = (category) => category === 'Sub Experiment'
