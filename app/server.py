import traceback
from flask import Flask, render_template, request, send_file, jsonify
import subprocess
import os
import urllib.parse
from datetime import datetime
import re  # For sanitizing the filename

# Initialize the Flask app and define directories for templates and static files.
app = Flask(__name__, template_folder='templates_ui', static_folder='static')

# ------------------------------------------------------------------------------
# Function: get_mimetype
# Returns the correct MIME type based on the desired target format.
# ------------------------------------------------------------------------------
def get_mimetype(selected_format):
    fmt = selected_format.lower()
    if fmt == "png":
        return "image/png"
    elif fmt == "docx":
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    elif fmt == "epub":
        return "application/epub+zip"
    elif fmt == "html":
        return "text/html"
    elif fmt == "odt":
        return "application/vnd.oasis.opendocument.text"
    elif fmt in ["latex", "rst"]:
        return "text/plain"
    else:  # Default: PDF
        return "application/pdf"

# ------------------------------------------------------------------------------
# Route: /debug/inspector
# Displays information about installed programs (Pandoc, convert/magick),
# including their paths and versions – for verifying the installation.
# ------------------------------------------------------------------------------
@app.route("/debug/inspector", methods=["GET"])
def debug_inspector():
    logs = []
    try:
        pandoc_check = subprocess.run(["pandoc", "--version"], capture_output=True, text=True, check=True)
        logs.append("Pandoc found. Version/output:\n" + pandoc_check.stdout)
    except FileNotFoundError:
        logs.append("Pandoc was NOT found. (FileNotFoundError)")
    except subprocess.CalledProcessError as e:
        logs.append("Error calling 'pandoc --version':\n" + e.stderr)

    convert_which = subprocess.run(["which", "convert"], capture_output=True, text=True)
    logs.append("\nwhich convert:\n" + convert_which.stdout.strip())
    if convert_which.stdout.strip():
        convert_version = subprocess.run(["convert", "--version"], capture_output=True, text=True)
        logs.append("convert --version:\n" + convert_version.stdout)
    else:
        logs.append("Command 'convert' not in PATH.")

    magick_which = subprocess.run(["which", "magick"], capture_output=True, text=True)
    logs.append("\nwhich magick:\n" + (magick_which.stdout.strip() if magick_which.stdout else ""))
    if magick_which.stdout.strip():
        magick_version = subprocess.run(["magick", "--version"], capture_output=True, text=True)
        logs.append("magick --version:\n" + magick_version.stdout)
    else:
        logs.append("Command 'magick' not in PATH.")

    return "<pre>" + "\n".join(logs) + "</pre>"

# ------------------------------------------------------------------------------
# Route: /
# Displays the index template and lists all available LaTeX templates in the 
# directory /app/latex_templates.
# ------------------------------------------------------------------------------
@app.route("/")
def index():
    template_dir = "/app/latex_templates"
    try:
        available_templates = [
            f for f in os.listdir(template_dir)
            if f.endswith(".tex") or f.endswith(".latex")
        ]
    except Exception:
        available_templates = []
    return render_template("index.html", available_templates=available_templates)

# ------------------------------------------------------------------------------
# Function: get_conversion_params
# Builds the parameters for the Pandoc call – depending on the desired format,
# the original filename, and optionally a selected template.
# The original filename is "sanitized" to avoid issues with special characters.
# ------------------------------------------------------------------------------
def get_conversion_params(selected_format, original_filename, chosen_template=None):
    print(f"[DEBUG] get_conversion_params(selected_format={selected_format}, original_filename={original_filename}, chosen_template={chosen_template})")
    selected_format = selected_format.lower()
    pandoc_cmd_options = []
    extension = selected_format

    if selected_format == "pdf":
        pandoc_cmd_options = ["--pdf-engine=xelatex"]
    elif selected_format == "png":
        # For PNG, a PDF is generated internally, hence the extension "pdf"
        extension = "pdf"
        pandoc_cmd_options = ["--pdf-engine=xelatex"]
    elif selected_format in ["docx", "epub", "html", "odt", "latex", "rst"]:
        pass
    else:
        selected_format = "pdf"
        extension = "pdf"
        pandoc_cmd_options = ["--pdf-engine=xelatex"]

    # Generate dynamic filenames for all formats
    safe_name = re.sub(r'[^\w\-_\.]', '_', original_filename.rsplit('.', 1)[0])
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_filename = f"{timestamp}_{safe_name}.{extension}"

    template_arg = []
    if chosen_template and selected_format in ["pdf", "latex"]:
        template_path = os.path.join("/app/latex_templates", chosen_template)
        template_arg = ["--template", template_path]

    print(f"[DEBUG] extension={extension}, output_filename={output_filename}, pandoc_cmd_options={pandoc_cmd_options}, template_arg={template_arg}")
    return extension, output_filename, pandoc_cmd_options, template_arg

# ------------------------------------------------------------------------------
# Route: /convert (POST)
# Receives an uploaded Markdown file and converts it to the 
# desired format (PDF, DOCX, PNG, etc.) using Pandoc.
# If PNG is selected, the generated PDF is converted to PNG,
# applying the options "-density 300", "-strip", "-colorspace sRGB", and "-flatten".
# The file is then sent to the client.
# ------------------------------------------------------------------------------
@app.route("/convert", methods=["POST"])
def convert():
    try:
        print("[DEBUG] /convert called")
        md_file = request.files.get("markdown_file")
        if not md_file:
            print("[DEBUG] No file uploaded")
            return "No file uploaded", 400

        original_filename = md_file.filename
        selected_format = request.form.get("format", "pdf")
        chosen_template = request.form.get("template")
        print(f"[DEBUG] original_filename={original_filename}, selected_format={selected_format}, chosen_template={chosen_template}")

        extension, output_filename, pandoc_cmd_options, template_arg = get_conversion_params(
            selected_format, original_filename, chosen_template
        )

        input_path = "/tmp/temp.md"
        output_path = f"/tmp/{output_filename}"

        print("[DEBUG] Saving uploaded markdown to", input_path)
        md_file.save(input_path)

        cmd = ["pandoc", input_path, "-o", output_path] + pandoc_cmd_options + template_arg
        print("[DEBUG] Running pandoc command:", cmd)
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("[DEBUG] Pandoc stdout:\n", result.stdout)
        if result.stderr:
            print("[DEBUG] Pandoc stderr:\n", result.stderr)

        # If PNG is selected as the target format, perform the conversion:
        if selected_format.lower() == "png":
            png_output_path = output_path.rsplit('.', 1)[0] + ".png"
            print("[DEBUG] Converting PDF -> PNG:", output_path, "to", png_output_path)
            try:
                result = subprocess.run(
                    ["convert", "-density", "300", "-strip", "-colorspace", "sRGB", "-flatten", output_path, png_output_path],
                    check=True, capture_output=True, text=True
                )
                print("[DEBUG] convert stdout:\n", result.stdout)
                if result.stderr:
                    print("[DEBUG] convert stderr:\n", result.stderr)
            except FileNotFoundError:
                print("[DEBUG] 'convert' not found, trying 'magick convert'")
                result = subprocess.run(
                    ["magick", "convert", "-density", "300", "-strip", "-colorspace", "sRGB", "-flatten", output_path, png_output_path],
                    check=True, capture_output=True, text=True
                )
                print("[DEBUG] magick convert stdout:\n", result.stdout)
                if result.stderr:
                    print("[DEBUG] magick convert stderr:\n", result.stderr)
            if not os.path.exists(png_output_path):
                print("[ERROR] PNG file was not created:", png_output_path)
                return "Error in PNG conversion: File was not created.", 500
            # Generate a dynamic filename for the PNG output
            output_filename = output_filename.rsplit('.', 1)[0] + ".png"
            output_path = png_output_path

        mimetype = get_mimetype(selected_format)
        print(f"[DEBUG] Using MIME type: {mimetype}")

        print("[DEBUG] Sending file:", output_path)
        response = send_file(output_path, as_attachment=True, download_name=output_filename, mimetype=mimetype)
        encoded_filename = urllib.parse.quote(output_filename)
        response.headers["Content-Disposition"] = (
            f'attachment; filename="{output_filename}"; filename*=UTF-8\'\'{encoded_filename}'
        )
        return response

    except subprocess.CalledProcessError as cpe:
        print("[ERROR] subprocess.CalledProcessError:", cpe)
        print("[ERROR] stderr:", cpe.stderr)
        traceback.print_exc()
        return f"Error during conversion (CalledProcessError): {cpe.stderr}", 500

    except Exception as e:
        print("[ERROR] Exception in /convert route")
        traceback.print_exc()
        return f"Unknown error in /convert: {e}", 500

# ------------------------------------------------------------------------------
# Route: /api/convert (POST)
# Similar to /convert, but for API requests that receive JSON data.
# ------------------------------------------------------------------------------
@app.route("/api/convert", methods=["POST"])
def api_convert():
    try:
        print("[DEBUG] /api/convert called")
        data = request.get_json()
        if not data or "markdown" not in data:
            return jsonify({"error": "No Markdown data found"}), 400

        original_filename = data.get("filename", "imported")
        selected_format = data.get("format", "pdf")
        chosen_template = data.get("template")
        print(f"[DEBUG] data.filename={original_filename}, data.format={selected_format}, data.template={chosen_template}")

        extension, output_filename, pandoc_cmd_options, template_arg = get_conversion_params(
            selected_format, original_filename, chosen_template
        )

        input_path = "/tmp/temp.md"
        output_path = f"/tmp/{output_filename}"

        with open(input_path, "w", encoding="utf-8") as f:
            f.write(data["markdown"])
        print("[DEBUG] Wrote markdown to", input_path)

        cmd = ["pandoc", input_path, "-o", output_path] + pandoc_cmd_options + template_arg
        print("[DEBUG] Running pandoc command:", cmd)
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("[DEBUG] Pandoc stdout:\n", result.stdout)
        if result.stderr:
            print("[DEBUG] Pandoc stderr:\n", result.stderr)

        if selected_format.lower() == "png":
            png_output_path = output_path.rsplit('.', 1)[0] + ".png"
            print("[DEBUG] Converting PDF -> PNG:", output_path, "to", png_output_path)
            try:
                result = subprocess.run(
                    ["convert", "-density", "300", "-strip", "-colorspace", "sRGB", "-flatten", output_path, png_output_path],
                    check=True, capture_output=True, text=True
                )
                print("[DEBUG] convert stdout:\n", result.stdout)
                if result.stderr:
                    print("[DEBUG] convert stderr:\n", result.stderr)
            except FileNotFoundError:
                print("[DEBUG] 'convert' not found, trying 'magick convert'")
                result = subprocess.run(
                    ["magick", "convert", "-density", "300", "-strip", "-colorspace", "sRGB", "-flatten", output_path, png_output_path],
                    check=True, capture_output=True, text=True
                )
                print("[DEBUG] magick convert stdout:\n", result.stdout)
                if result.stderr:
                    print("[DEBUG] magick convert stderr:\n", result.stderr)
            if not os.path.exists(png_output_path):
                print("[ERROR] PNG file was not created:", png_output_path)
                return jsonify({"error": "Error in PNG conversion: File was not created."}), 500
            output_filename = output_filename.rsplit('.', 1)[0] + ".png"
            output_path = png_output_path

        mimetype = get_mimetype(selected_format)
        print(f"[DEBUG] Using MIME type: {mimetype}")

        print("[DEBUG] Sending file:", output_path)
        return send_file(output_path, as_attachment=True, download_name=output_filename, mimetype=mimetype)

    except subprocess.CalledProcessError as cpe:
        print("[ERROR] subprocess.CalledProcessError:", cpe)
        print("[ERROR] stderr:", cpe.stderr)
        traceback.print_exc()
        return jsonify({"error": f"Error during conversion (CalledProcessError): {cpe.stderr}"}), 500

    except Exception as e:
        print("[ERROR] Exception in /api/convert route")
        traceback.print_exc()
        return jsonify({"error": f"Unknown error in /api/convert: {e}"}), 500

# ------------------------------------------------------------------------------
# Start Flask in debug mode
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8777, debug=False)
