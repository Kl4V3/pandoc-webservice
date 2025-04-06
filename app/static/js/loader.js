document.addEventListener("DOMContentLoaded", function() {
  // Retrieve DOM elements from the form and the loader
  var form = document.getElementById('demo-upload');
  var loader = document.getElementById('loader');
  var cancelBtn = document.getElementById('cancel-btn');
  var controller;  // Will later be used as an AbortController for the fetch request

  // Function to display a brief popup with a message
  function showPopup(message) {
    var popup = document.createElement('div');
    popup.className = 'popup';
    popup.innerText = message;
    document.body.appendChild(popup);
    // Fade out and remove after 2 seconds
    setTimeout(function(){
      popup.style.opacity = '0';
      setTimeout(function(){
        popup.remove();
      }, 500);
    }, 2000);
  }

  // Event listener triggered when the form is submitted
  form.addEventListener('submit', function(e) {
    e.preventDefault(); // Prevent default form submission

    // Create a new AbortController to later abort the request if needed
    controller = new AbortController();
    var signal = controller.signal;
    loader.style.display = 'flex'; // Show the loader

    var formData = new FormData(form);
    fetch(form.action, {
      method: 'POST',
      body: formData,
      signal: signal
    })
    .then(function(response) {
      if (!response.ok) {
        throw new Error('Network response was not ok');
      }
      // Read the Content-Disposition header to extract the filename
      var disposition = response.headers.get('Content-Disposition');
      var filename = "download"; // Fallback if no filename is found
      if (disposition && disposition.indexOf('attachment') !== -1) {
        var filenameRegex = /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/;
        var matches = filenameRegex.exec(disposition);
        if (matches != null && matches[1]) {
          filename = matches[1].replace(/['"]/g, '');
        }
      }
      // Read the response body as a Blob and package it together with the extracted filename
      return response.blob().then(function(blob) {
        return { blob: blob, filename: filename };
      });
    })
    .then(function(obj) {
      loader.style.display = 'none'; // Hide the loader
      showPopup('Conversion Successful');
      // Create a URL for the Blob and generate an invisible download link
      var url = window.URL.createObjectURL(obj.blob);
      var a = document.createElement('a');
      a.href = url;
      a.download = obj.filename; // Use the filename extracted from the header
      document.body.appendChild(a);
      a.click();
      a.remove();
      // Release the URL after a short delay
      setTimeout(function() {
        window.URL.revokeObjectURL(url);
      }, 1000);
    })
    .catch(function(error) {
      loader.style.display = 'none'; // Hide the loader in case of error
      if (error.name === 'AbortError') {
        showPopup('Upload Cancelled');
      } else {
        showPopup('Conversion Error');
        console.error('Error:', error);
      }
    });
  });

  // Event listener for the "Cancel" button to abort the current request
  cancelBtn.addEventListener('click', function() {
    if (controller) {
      controller.abort();
    }
  });
});
