let backendConfig = {
  ports: [],
  sensors: [],
  equations: [],
  graphs: [],
  read_rate_hz: "--",
  active_graphs: 0,
};

let activeLeftTab = "sensors";
let editingSensorId = null;
let editingEquationId = null;
let currentGraphPage = 0;
let selectedValueGraphIds = [null, null, null];
const GRAPHS_PER_PAGE = 10;

const chartInstances = {};
let wsConnection = null;
