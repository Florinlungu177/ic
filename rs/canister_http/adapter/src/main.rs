/// This binary is managed by systemd and added to the replica image.
/// The replica communicates with the HTTP adapter over unix domain sockets.
/// Relevant configuration files:
/// systemd service ic-os/guestos/rootfs/etc/systemd/system/ic-canister-http-adapter.service
/// systemd socket ic-os/guestos/rootfs/etc/systemd/system/ic-canister-http-adapter.socket
use tonic::transport::Server;

use ic_async_utils::{ensure_single_named_systemd_socket, incoming_from_first_systemd_socket};
use ic_canister_http_adapter::{proto::http_adapter_server::HttpAdapterServer, HttpFromCanister};

const IC_CANISTER_HTTP_SOCKET_NAME: &str = "ic-canister-http-adapter.socket";

#[tokio::main]
pub async fn main() {
    // TODO: add logs (NET-853)
    // TODO: add config/CLI (NET-880)

    // Make sure we receive the correct socket from systemd (and only one).
    // This function panics if multiple sockets are passed to this process or a wrongly named socket is passed.
    ensure_single_named_systemd_socket(IC_CANISTER_HTTP_SOCKET_NAME);

    // Creates an async stream from the socket file descripter passed to this process by systemd (as FD #3).
    // Make sure to only call this function once in this process. Calling it multiple times leads to multiple socket listeners
    let incoming = incoming_from_first_systemd_socket();

    let http_from_canister = HttpFromCanister::new();
    let server = Server::builder()
        .add_service(HttpAdapterServer::new(http_from_canister))
        .serve_with_incoming(incoming);

    // Run this server for... forever!
    if let Err(e) = server.await {
        eprintln!("server error: {}", e);
    }
}
