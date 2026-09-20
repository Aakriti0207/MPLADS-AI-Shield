/**
 * Approximate geographic centre of each State / UT, used ONLY to place
 * one summary circle per state on the public map.
 *
 * The public MPLADS dataset carries no project-level coordinates, so the
 * portal never plots individual projects as points. These are reference
 * positions for whole states (approximate, for display) -- not data
 * about any project. Keys match the state labels the API returns.
 */
export const STATE_CENTROIDS = {
  'Andaman And Nicobar Islands': [11.7, 92.7],
  'Andhra Pradesh': [15.9, 79.7],
  'Arunachal Pradesh': [28.2, 94.7],
  Assam: [26.2, 92.9],
  Bihar: [25.1, 85.3],
  Chandigarh: [30.73, 76.78],
  Chhattisgarh: [21.3, 81.9],
  'Dadra And Nagar Haveli And Daman And Diu': [20.4, 72.9],
  Delhi: [28.65, 77.2],
  Goa: [15.35, 74.05],
  Gujarat: [22.7, 71.6],
  Haryana: [29.06, 76.1],
  'Himachal Pradesh': [31.9, 77.2],
  'Jammu And Kashmir': [33.9, 75.1],
  Jharkhand: [23.6, 85.3],
  Karnataka: [14.9, 75.7],
  Kerala: [10.4, 76.4],
  Ladakh: [34.4, 77.6],
  Lakshadweep: [10.6, 72.6],
  'Madhya Pradesh': [23.5, 78.3],
  Maharashtra: [19.4, 76.0],
  Manipur: [24.75, 93.9],
  Meghalaya: [25.5, 91.3],
  Mizoram: [23.3, 92.8],
  Nagaland: [26.1, 94.5],
  Odisha: [20.5, 84.4],
  Puducherry: [11.93, 79.8],
  Punjab: [31.0, 75.4],
  Rajasthan: [26.6, 73.8],
  Sikkim: [27.55, 88.5],
  'Tamil Nadu': [10.9, 78.4],
  Telangana: [17.9, 79.1],
  Tripura: [23.75, 91.7],
  'Uttar Pradesh': [26.9, 80.6],
  Uttarakhand: [30.1, 79.2],
  'West Bengal': [23.8, 87.9],
}

export const INDIA_BOUNDS = [[6.5, 68.0], [36.0, 97.6]]