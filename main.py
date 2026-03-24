

# Andrew Bierer 2026

from phew import server, logging, access_point, dns, connect_to_wifi, is_connected_to_wifi
from phew.template import render_template
import json, os, _thread, machine, utime, gc, sys, network, socket # type: ignore
from machine import SPI, Pin # type: ignore
gc.threshold(50000) # setup garbage collection

APP_TEMPLATE_PATH = "app_templates" # Directory where HTML templates are stored
AP_NAME = "Open_Irr RaspPi Pico AP" # Access point name
WIFI_FILE = "wifi.json" # File to store WiFi credentials on Pico
SETTINGS_FILE = "settings.json" # File to store settings on Pico
READING_FILE = "reading.json" # Active settings file

global_ip_address = None # Global variable to track current IP address?

MOSI_PIN = 3 #TX
MISO_PIN = 4 #RX
onboard_led = machine.Pin("LED", machine.Pin.OUT)

# resets pico, working getting switch to work (pontentially delete or ignore)
def machine_reset():
    utime.sleep(5) # waits a second before going forward 
    print("Resetting...")
    machine.reset() # turns off pi

# starting page 
def app_index(request):
    return render_template(f"{APP_TEMPLATE_PATH}/index.html")

# configure the wifi connection
def app_configure(request):
    # Save WiFi credentials first
    with open(WIFI_FILE, "w") as f:
        json.dump(request.form, f)
    
    ssid = request.form.get("ssid", "")
    wlan = network.WLAN(network.STA_IF)
    
    # Check if already connected
    if wlan.isconnected():
        ip = wlan.ifconfig()[0]  # Get current IP
        return render_template(f"{APP_TEMPLATE_PATH}/alreadyConnected.html", ssid=ssid, ip=ip)
    
    # Start connection if not already connected
    if not wlan.active() or not wlan.isconnected():
        def _connect_to_wifi():
            try:
                connect_to_wifi(request.form["ssid"], request.form["password"])
            except Exception as e:
                logging.error(f"Connection failed: {str(e)}")
        _thread.start_new_thread(_connect_to_wifi, ())
    # Show connection status page with auto-refresh
    current_ip = wlan.ifconfig()[0] if wlan.isconnected() else "Not assigned yet"
    return render_template(f"{APP_TEMPLATE_PATH}/connecting.html", ssid=ssid, current_ip=current_ip)

# LED toggle, can ignore/delete
def app_toggle_led(request):
        onboard_led.toggle()
        return "OK"

# reset wifi config 
def app_reset(request):
    """Immediately serves the reset page, then triggers async reset"""
    # Start reset sequence after small delay (allows page to load)
    _thread.start_new_thread(_delayed_reset, ())
    
    return render_template(
        f"{APP_TEMPLATE_PATH}/reset.html",
        access_point_ssid=AP_NAME,
        ip="192.168.4.1",  # Default AP IP
        reconnect_delay=3   # Seconds before auto-reconnect attempt
    )

# delay reset to show reset.html
def _delayed_reset():
    """Threaded reset with proper timing"""
    utime.sleep(1.5)  # Critical: Allow page to fully load first
    _perform_network_reset()
    sys.exit()

# disconnect from wifi & reset
def _perform_network_reset():
    """Atomic reset operations"""
    try:
        # 1. Delete credentials
        if WIFI_FILE in os.listdir():
            os.remove(WIFI_FILE)
        
        # 2. Controlled disconnect
        wlan = network.WLAN(network.STA_IF)
        if wlan.isconnected():
            wlan.disconnect()
            utime.sleep(1)  # Allow graceful disconnect
            
        # 3. Ensure interface down
        wlan.active(False)
        utime.sleep(0.5)
        
        # 4. Restart AP
        global ap
        ap = access_point(AP_NAME)
        logging.info("AP restarted successfully")
        
    except Exception as e:
        logging.error(f"Reset failed: {str(e)}")

# options page 
def app_change_options(request):
    return render_template(f"{APP_TEMPLATE_PATH}/options.html")


# internal temperature sensor on pico
def app_get_temperature(request):
    sensor_temp = machine.ADC(4)
    reading = sensor_temp.read_u16() * (3.3 / (65535))
    temperature = 27 - (reading - 0.706)/0.001721
    return f"{round(temperature, 1)}"

def app_catch_all(request):
        return "Not found.", 404

def app_dashboard(request):
    return render_template(f"{APP_TEMPLATE_PATH}/dashboard.html")

def app_file_access(request):
    return render_template(f"{APP_TEMPLATE_PATH}/fileAccess.html", files = sorted(os.listdir()))


# Routes to different pages
server.add_route("/", handler = app_index, methods = ["POST", "GET"]) #index page, also handles form submission for wifi credentials
server.add_route("/configure", handler = app_configure, methods= ["POST", "GET"]) #alreadyConnected & connecting html pages 
server.add_route("/reset", handler = app_reset, methods = ["GET"]) # reset page, also handles the reset process in a separate thread to allow the page to load first
server.add_route("/toggle", handler = app_toggle_led, methods = ["GET"]) # toggle onboard LED for testing purposes, can ignore/delete
server.add_route("/temperature", handler = app_get_temperature, methods = ["GET"]) # returns the current temperature reading from the internal sensor, can be used for testing or future features, can ignore/delete
server.add_route("/options", handler = app_change_options, methods= ["POST", "GET"]) # options page
server.add_route("/dashboard", handler = app_dashboard, methods= ["POST", "GET"]) # dashboard page
server.add_route("/files", handler = app_file_access, methods= ["POST", "GET"]) # fileAccess page
server.set_callback(app_catch_all) # catch-all for undefined routes, returns 404

# Set to Accesspoint mode
ap = access_point(f"{AP_NAME}")  # Change this to whatever Wi-Fi SSID you wish
ip = ap.ifconfig()[0]                   # Grab the IP address and store it
logging.info(f"starting DNS server on {ip}")
dns.run_catchall(ip)                    # Catch all requests and reroute them
server.run()                            # Run the server
logging.info("Webserver Started")