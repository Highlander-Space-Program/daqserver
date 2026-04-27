let backendConfig = {
    ports: [],
    sensors: [],
    equations: [],
    graphs: [],
    read_rate_hz: "--",
    active_graphs: 0
};

let activeLeftTab = "sensors";
let editingSensorId = null;
let editingEquationId = null;
let editingGraphId = null;
let currentGraphPage = 0;
const GRAPHS_PER_PAGE = 4;