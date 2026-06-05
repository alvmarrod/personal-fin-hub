const sidebarOpen = $state(false);
const modalStack = $state([]);

export function getUIState() {
  return {
    get sidebarOpen() { return sidebarOpen; },
    set sidebarOpen(v) { sidebarOpen = v; },
    toggleSidebar() { sidebarOpen = !sidebarOpen; },
    get modalStack() { return modalStack; },
    pushModal(id) { modalStack = [...modalStack, id]; },
    popModal() { modalStack = modalStack.slice(0, -1); },
  };
}
