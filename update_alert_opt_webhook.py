import json
import meraki
import datetime

def log_result(log_file, message):
    with open(log_file, 'a') as f:
        f.write(message + '\n')

def get_all_organizations(dashboard):
    return dashboard.organizations.getOrganizations()

def get_networks_in_org(dashboard, org_id):
    return dashboard.organizations.getOrganizationNetworks(org_id)

def load_alert_settings_from_file(filepath):
    with open(filepath, 'r') as f:
        return json.load(f)

def create_webhook(dashboard, network_id, name, url, shared_secret='defaultSecret123'):
    try:
        existing_hooks = dashboard.networks.getNetworkWebhooksHttpServers(network_id)
        for hook in existing_hooks:
            if hook['name'] == name or hook['url'] == url:
                print(f"ℹ️ Webhook already exists (name or URL match): {hook['name']} — Reusing.")
                return hook

        response = dashboard.networks.createNetworkWebhooksHttpServer(
            network_id,
            name=name,
            url=url,
            sharedSecret=shared_secret,
            payloadTemplate={
                'payloadTemplateId': 'wpt_00001',
                'name': 'Meraki (included)'
            }
        )
        print(f"✅ Created webhook '{name}' at {url} for network {network_id}")
        return response
    except Exception as e:
        print(f"❌ Error creating webhook for network {network_id}: {e}")
        return None

def update_network_alert_settings(dashboard, network_id, alert_settings):
    try:
        dashboard.networks.updateNetworkAlertsSettings(network_id, **alert_settings)
        return True
    except Exception as e:
        print(f"❌ Error updating alert settings for network {network_id}: {e}")
        return False

def main():
    api_key = input("Enter your Meraki Dashboard API Key: ").strip()
    config_file = input("Enter path to alert config JSON file (e.g. alerts_config.json): ").strip()
    dry_run = input("Enable dry-run mode (no changes applied)? (y/n): ").strip().lower() == 'y'

    alert_settings = load_alert_settings_from_file(config_file)

    print("\n📋 Loaded Alert Settings Configuration:\n")
    print(json.dumps(alert_settings, indent=2))

    confirm = input("❓ Proceed with these alert settings? (yes/no): ").strip().lower()
    if confirm != 'yes':
        print("⚠️ Aborted by user.")
        return

    dashboard = meraki.DashboardAPI(api_key, output_log=False, print_console=True)

    orgs = get_all_organizations(dashboard)
    print("\nAvailable Organizations:")
    for idx, org in enumerate(orgs):
        print(f"{idx + 1}: {org['name']} (ID: {org['id']})")
    org_index = int(input("\nSelect an organization by number: ")) - 1
    org_id = orgs[org_index]['id']

    networks = get_networks_in_org(dashboard, org_id)
    print("\nAvailable Networks:")
    for idx, net in enumerate(networks):
        print(f"{idx + 1}: {net['name']} (ID: {net['id']})")

    choice = input("\n Do you want to UPDATE alert settings for ALL networks? (y/n): ").strip().lower()
    if choice == 'y':
        selected_networks = networks
    else:
        indices = input("Enter the numbers of the networks to update, separated by commas: ")
        indices = [int(i.strip()) - 1 for i in indices.split(',') if i.strip().isdigit()]
        selected_networks = [networks[i] for i in indices]

    # Prepare log
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = f"alert_update_log_{timestamp}.txt"
    log_result(log_file, f"=== Alert Update Log: {timestamp} ===")
    log_result(log_file, f"Dry Run Mode: {'YES' if dry_run else 'NO'}\n")

    # Optional Webhook input
    use_webhook = input("Do you want to create/link a webhook to alerts? (y/n): ").strip().lower() == 'y'
    webhook_name = None
    webhook_url = None
    webhook_secret = None

    # Final confirmation before applying
    print("\n🚨 FINAL CHECK")
    print("The script is about to apply changes to the following networks:")
    for net in selected_networks:
        print(f"- {net['name']} (ID: {net['id']})")

    final_confirm = input(
        "\n⚠️ Are you sure you want to proceed with these changes? Type 'CONFIRM' to continue: ").strip()
    if final_confirm != 'CONFIRM':
        print("❌ Aborted by user at final validation step.")
        return

    # Apply changes
    for network in selected_networks:
        net_id = network['id']
        net_name = network['name']
        print(f"\n🔧 Processing: {net_name} (ID: {net_id})")

        if dry_run:
            msg = f"🟡 DRY RUN: Would {'create webhook and ' if use_webhook else ''}update alerts for '{net_name}'"
            print(msg)
            log_result(log_file, msg)
            continue

        webhook_id = None
        if use_webhook:
            if not webhook_name:
                webhook_name = input("Enter a name for the webhook to be created: ").strip()
                webhook_url = input("Enter the webhook destination URL (e.g. https://webhook.site/...): ").strip()
                webhook_secret = input("Enter a shared secret for the webhook (or press enter for default): ").strip() or 'defaultSecret123'

            webhook_response = create_webhook(dashboard, net_id, webhook_name, webhook_url, webhook_secret)
            if not webhook_response:
                log_result(log_file, f"❌ Skipped updating alerts for {net_name} due to webhook failure.")
                continue
            webhook_id = webhook_response.get("id")

        # # Inject webhook ID into alert config if applicable
        # if webhook_id:
        #     for alert in alert_settings.get("alerts", []):
        #         destinations = alert.setdefault("alertDestinations", {})
        #         hooks = destinations.setdefault("httpServerIds", [])
        #         if webhook_id not in hooks:
        #             hooks.append(webhook_id)

        success = update_network_alert_settings(dashboard, net_id, alert_settings)
        if success:
            log_result(log_file, f"✅ Updated alerts for {net_name}")
        else:
            log_result(log_file, f"❌ Failed to update alerts for {net_name}")

    print(f"\n📝 Log saved to: {log_file}")

if __name__ == "__main__":
    main()