FROM miktex/miktex:latest

# Install additional packages, including Python3, pip, pandoc, curl, wget, perl, imagemagick, ghostscript, and nano
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    pandoc \
    curl \
    wget \
    perl \
    imagemagick \
    ghostscript \
    nano \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Optional: Set the PATH so that ImageMagick commands (e.g., convert) can be found
ENV PATH="/usr/bin:${PATH}"

# Set the working directory
WORKDIR /app

# Adjust the ImageMagick policy: Allow PDF processing
RUN sed -i 's/<policy domain="coder" rights="none" pattern="PDF" \/>/<policy domain="coder" rights="read|write" pattern="PDF" \/>/g' /etc/ImageMagick-6/policy.xml

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Optional: Install Gunicorn if it's not already listed in requirements.txt
RUN pip3 install gunicorn

# Copy the application code into the container
COPY app/ /app/

# Expose port 8777
EXPOSE 8777

# Start the application with Gunicorn as the production server
CMD ["gunicorn", "--bind", "0.0.0.0:8777", "server:app"]
