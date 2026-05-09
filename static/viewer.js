const pieceImages = {
  K: "/pieces/cburnett/wK.svg",
  Q: "/pieces/cburnett/wQ.svg",
  R: "/pieces/cburnett/wR.svg",
  B: "/pieces/cburnett/wB.svg",
  N: "/pieces/cburnett/wN.svg",
  P: "/pieces/cburnett/wP.svg",
  k: "/pieces/cburnett/bK.svg",
  q: "/pieces/cburnett/bQ.svg",
  r: "/pieces/cburnett/bR.svg",
  b: "/pieces/cburnett/bB.svg",
  n: "/pieces/cburnett/bN.svg",
  p: "/pieces/cburnett/bP.svg"
};

const boardEl = document.getElementById("board");
const statusEl = document.getElementById("status");
const tabsEl = document.getElementById("board-tabs");
const deviceEl = document.getElementById("device");
const updatedEl = document.getElementById("updated");
const reportsEl = document.getElementById("reports");
const materialEl = document.getElementById("material");
const fenEl = document.getElementById("fen");
const eventsEl = document.getElementById("events");
const flipButton = document.getElementById("flip");

let boards = {};
let activeBoard = 0;
let flipped = false;
let previousBoard = {};

flipButton.addEventListener("click", () => {
  flipped = !flipped;
  render();
});

function squareName(file, rank) {
  return "abcdefgh"[file] + String(rank + 1);
}

function parseFen(fen) {
  const board = {};
  const placement = String(fen || "").split(/\s+/)[0];
  const ranks = placement.split("/");
  if (ranks.length !== 8) return board;

  for (let row = 0; row < 8; row += 1) {
    let file = 0;
    const rank = 7 - row;
    for (const char of ranks[row]) {
      if (/\d/.test(char)) {
        file += Number(char);
      } else {
        board[squareName(file, rank)] = char;
        file += 1;
      }
    }
  }
  return board;
}

function render() {
  renderTabs();
  const current = boards[activeBoard];
  const board = current ? parseFen(current.fen) : {};
  const changed = new Set();

  for (const square of new Set([...Object.keys(previousBoard), ...Object.keys(board)])) {
    if (previousBoard[square] !== board[square]) changed.add(square);
  }

  boardEl.innerHTML = "";
  const ranks = flipped ? [...Array(8).keys()] : [...Array(8).keys()].reverse();
  const files = flipped ? [...Array(8).keys()].reverse() : [...Array(8).keys()];

  for (const rank of ranks) {
    for (const file of files) {
      const name = squareName(file, rank);
      const square = document.createElement("div");
      square.className = `square ${(file + rank) % 2 ? "light" : "dark"}`;
      if (changed.has(name)) square.classList.add("changed");
      square.setAttribute("aria-label", name);

      const piece = board[name];
      if (piece) {
        const img = document.createElement("img");
        img.className = "piece";
        img.alt = piece;
        img.draggable = false;
        img.src = pieceImages[piece];
        square.appendChild(img);
      }
      if (file === (flipped ? 7 : 0) || rank === (flipped ? 7 : 0)) {
        const coord = document.createElement("span");
        coord.className = "coord";
        coord.textContent = file === (flipped ? 7 : 0) ? String(rank + 1) : "abcdefgh"[file];
        square.appendChild(coord);
      }
      boardEl.appendChild(square);
    }
  }

  previousBoard = board;
  renderSidePanel(current, board);
}

function renderTabs() {
  tabsEl.innerHTML = "";
  const ids = Object.keys(boards).map(Number).sort((a, b) => a - b);
  if (ids.length === 0) {
    const tab = document.createElement("button");
    tab.type = "button";
    tab.className = "tab active";
    tab.textContent = "Board 0";
    tabsEl.appendChild(tab);
    return;
  }

  for (const id of ids) {
    const tab = document.createElement("button");
    tab.type = "button";
    tab.className = `tab ${id === activeBoard ? "active" : ""}`;
    tab.textContent = `Board ${id}`;
    tab.addEventListener("click", () => {
      activeBoard = id;
      previousBoard = {};
      render();
    });
    tabsEl.appendChild(tab);
  }
}

function renderSidePanel(current, board) {
  if (!current) {
    statusEl.textContent = "Waiting for board";
    statusEl.classList.remove("live");
    deviceEl.textContent = "Waiting";
    updatedEl.textContent = "Never";
    reportsEl.textContent = "0";
    fenEl.textContent = "";
    materialEl.innerHTML = "";
    return;
  }

  statusEl.textContent = "Live";
  statusEl.classList.add("live");
  deviceEl.textContent = `${current.name} ${current.identifier}`.trim();
  updatedEl.textContent = current.received_at || "Now";
  reportsEl.textContent = String(current.report_count || 0);
  fenEl.textContent = current.fen || "";

  const counts = countMaterial(board);
  materialEl.innerHTML = `
    <div>White <strong>${counts.white}</strong></div>
    <div>Black <strong>${counts.black}</strong></div>
    <div>Queens <strong>${counts.queens}</strong></div>
    <div>Pieces <strong>${counts.total}</strong></div>
  `;
}

function countMaterial(board) {
  const pieces = Object.values(board);
  return {
    white: pieces.filter(piece => piece === piece.toUpperCase()).length,
    black: pieces.filter(piece => piece === piece.toLowerCase()).length,
    queens: pieces.filter(piece => piece.toLowerCase() === "q").length,
    total: pieces.length
  };
}

function addLog(message) {
  const item = document.createElement("li");
  item.textContent = message;
  eventsEl.prepend(item);
  while (eventsEl.children.length > 12) {
    eventsEl.removeChild(eventsEl.lastChild);
  }
}

function applyPayload(payload) {
  if (payload.boards) {
    boards = payload.boards;
  }
  if (payload.board) {
    boards[payload.board.board_index] = payload.board;
    activeBoard = payload.board.board_index;
    addLog(`Board ${payload.board.board_index}: ${payload.board.fen}`);
  }
  if (payload.status) addLog(payload.status);
  if (!boards[activeBoard]) {
    const first = Object.keys(boards).map(Number).sort((a, b) => a - b)[0];
    if (Number.isInteger(first)) activeBoard = first;
  }
  render();
}

async function loadSnapshot() {
  const response = await fetch("/state");
  applyPayload(await response.json());
}

function connectEvents() {
  const source = new EventSource("/events");
  source.addEventListener("snapshot", event => applyPayload(JSON.parse(event.data)));
  source.addEventListener("board", event => applyPayload({ board: JSON.parse(event.data) }));
  source.addEventListener("status", event => applyPayload({ status: JSON.parse(event.data).message }));
  source.addEventListener("error", () => {
    statusEl.textContent = "Disconnected";
    statusEl.classList.remove("live");
  });
}

loadSnapshot();
connectEvents();
render();
