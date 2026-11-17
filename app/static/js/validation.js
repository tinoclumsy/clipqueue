/* validation.js - client-side form validation for ClipQueue.

   IMPORTANT: the Python code (the server) checks everything again.
   JavaScript can be switched off or changed by a visitor, so this file only makes
   the forms friendlier: the visitor sees what is wrong BEFORE sending the form. */

(function () {
    "use strict";

    // Patterns (the rules are the same as in the Python code)
    var EMAIL_PATTERN = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
    var PHONE_PATTERN = /^[0-9 +()-]*$/;
    var PRICE_PATTERN = /^\d+(\.\d{1,2})?$/;

    // Fields that need at least 5 characters
    var MIN_FIVE = ["question", "answer", "comment"];

    // Fields that need at least 2 characters
    var MIN_TWO = ["full_name", "display_name", "name"];


    /* ---------- Finding the fields ---------- */

    // Is this a field the visitor types into or chooses from?
    function isCheckable(field) {
        var type = field.type;
        return !(type === "hidden" || type === "submit" || type === "button" ||
                 type === "checkbox" || type === "radio" || field.disabled);
    }

    // All the checkable fields of a form
    function getFields(form) {
        return Array.prototype.filter.call(form.elements, function (element) {
            var tag = element.tagName;
            return (tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA") && isCheckable(element);
        });
    }


    /* ---------- The rules: returns a message, or "" when the field is fine ---------- */

    function findMessage(field, form) {
        var name = field.name;
        // Passwords keep their spaces. Everything else is trimmed.
        var value = field.type === "password" ? field.value : field.value.trim();

        // A number box with letters typed in
        if (field.validity && field.validity.badInput) {
            return "Please enter a valid number.";
        }

        // Schedule form: a day with a ticked box needs a start and end time
        var dayMatch = /^(start|end)_(\d+)$/.exec(name);
        if (dayMatch) {
            var working = form.elements["working_" + dayMatch[2]];
            if (!working || !working.checked) {
                return "";   // a day off needs no times
            }
            if (value === "") {
                return "Please enter a time.";
            }
            if (dayMatch[1] === "end") {
                var start = form.elements["start_" + dayMatch[2]];
                if (start && start.value && value <= start.value) {
                    return "The end time must be after the start time.";
                }
            }
            var minutes = value.slice(3, 5);
            if (minutes !== "00" && minutes !== "30") {
                return "Use the hour or half hour, like 09:00 or 09:30.";
            }
            return "";
        }

        // Required fields
        if (field.required && value === "") {
            return field.tagName === "SELECT" ? "Please choose an option." : "This field is required.";
        }

        // Empty optional fields are fine
        if (value === "") {
            return "";
        }

        // Email
        if ((name === "email" || field.type === "email") && !EMAIL_PATTERN.test(value)) {
            return "Please enter a valid email address, like name@example.com.";
        }

        // Length limits written in the HTML (minlength / maxlength). -1 means "not set".
        if (field.minLength > 0 && value.length < field.minLength) {
            return "Use at least " + field.minLength + " characters.";
        }
        if (field.maxLength > 0 && value.length > field.maxLength) {
            return "Use at most " + field.maxLength + " characters.";
        }

        if (MIN_TWO.indexOf(name) !== -1 && value.length < 2) {
            return "Please enter at least 2 characters.";
        }
        if (MIN_FIVE.indexOf(name) !== -1 && value.length < 5) {
            return "Please enter at least 5 characters.";
        }
        if (name === "phone" && !PHONE_PATTERN.test(value)) {
            return "Use only digits, spaces, + - and ( ).";
        }
        if (name === "price" && !PRICE_PATTERN.test(value)) {
            return "Enter a price like 250 or 250.50 (up to 2 decimals).";
        }

        // Number boxes: min and max written in the HTML
        if (field.type === "number") {
            var number = Number(value);
            if (isNaN(number)) {
                return "Please enter a number.";
            }
            var hasMin = field.min !== "";
            var hasMax = field.max !== "";
            if ((hasMin && number < Number(field.min)) || (hasMax && number > Number(field.max))) {
                if (hasMin && hasMax) {
                    return "Enter a number from " + field.min + " to " + field.max + ".";
                }
                return hasMin ? "The smallest number allowed is " + field.min + "."
                              : "The biggest number allowed is " + field.max + ".";
            }
        }

        // Passwords. The 8-character rule only applies where a password is CREATED
        // (a form with a "confirm password" box), not on the login form.
        var confirmBox = form.elements["confirm_password"];
        if ((name === "password" || name === "new_password") && confirmBox && value.length < 8) {
            return "Use at least 8 characters.";
        }
        if (name === "confirm_password") {
            var original = form.elements["password"] || form.elements["new_password"];
            if (original && field.value !== original.value) {
                return "The two passwords do not match.";
            }
        }
        if (name === "new_password") {
            var current = form.elements["current_password"];
            if (current && field.value === current.value) {
                return "The new password must be different from the current one.";
            }
        }

        return "";
    }


    /* ---------- Showing and clearing messages ---------- */

    // Each field gets one <p class="field-error"> that we fill or empty
    function errorElementFor(field) {
        if (!field._errorElement) {
            var paragraph = document.createElement("p");
            paragraph.className = "field-error";
            paragraph.setAttribute("role", "alert");
            // On the schedule form the message goes under the whole day row
            var place = field.closest(".day-row") || field;
            place.insertAdjacentElement("afterend", paragraph);
            field._errorElement = paragraph;
        }
        return field._errorElement;
    }

    function showError(field, message) {
        errorElementFor(field).textContent = message;
        field.classList.add("is-invalid");
        field.setAttribute("aria-invalid", "true");
    }

    function clearError(field) {
        if (field._errorElement) {
            field._errorElement.textContent = "";
        }
        field.classList.remove("is-invalid");
        field.removeAttribute("aria-invalid");
    }

    // Check one field and show or clear its message. Returns true if the field is fine.
    function checkField(field, form) {
        var message = findMessage(field, form);
        if (message) {
            showError(field, message);
        } else {
            clearError(field);
        }
        return message === "";
    }


    /* ---------- Extras: character counter and password strength ---------- */

    function addCounter(field) {
        if (field.tagName !== "TEXTAREA" || field.maxLength < 0) {
            return;
        }
        var counter = document.createElement("div");
        counter.className = "char-count";
        field.insertAdjacentElement("afterend", counter);

        function update() {
            var used = field.value.length;
            counter.textContent = used + " / " + field.maxLength;
            counter.classList.toggle("is-near-limit", used > field.maxLength * 0.9);
        }
        field.addEventListener("input", update);
        update();
    }

    function addStrengthMeter(field) {
        var box = document.createElement("div");
        box.className = "strength";
        box.innerHTML = '<span class="strength-bar"></span><span class="strength-text"></span>';
        field.insertAdjacentElement("afterend", box);

        var bar = box.querySelector(".strength-bar");
        var text = box.querySelector(".strength-text");

        field.addEventListener("input", function () {
            var password = field.value;
            var score = 0;
            if (password.length >= 8) { score += 1; }
            if (password.length >= 12) { score += 1; }
            if (/[a-z]/.test(password) && /[A-Z]/.test(password)) { score += 1; }
            if (/\d/.test(password)) { score += 1; }
            if (/[^A-Za-z0-9]/.test(password)) { score += 1; }

            var level = "";
            if (password !== "") {
                level = score <= 2 ? "weak" : (score === 3 ? "okay" : "strong");
            }
            bar.style.setProperty("--score", password === "" ? 0 : score);
            bar.setAttribute("data-level", level);
            text.textContent = level.charAt(0).toUpperCase() + level.slice(1);
        });
    }


    /* ---------- Connecting everything to one form ---------- */

    function enhanceForm(form) {
        var fields = getFields(form);
        if (fields.length === 0) {
            return;   // forms with only buttons (Delete, Approve...) are left alone
        }

        // Switch off the browser's own pop-up bubbles. Our messages replace them.
        form.noValidate = true;

        fields.forEach(function (field) {
            addCounter(field);

            var isNewPassword = (field.name === "password" || field.name === "new_password");
            if (isNewPassword && form.elements["confirm_password"]) {
                addStrengthMeter(field);
            }

            // Check when the visitor leaves the box, or picks from a list
            field.addEventListener("blur", function () { checkField(field, form); });
            field.addEventListener("change", function () { checkField(field, form); });

            // While typing: update a message that is already showing
            field.addEventListener("input", function () {
                if (field.classList.contains("is-invalid")) {
                    checkField(field, form);
                }
                // When the password changes, the "confirm" box must be compared again
                if (isNewPassword && form.elements["confirm_password"]
                        && form.elements["confirm_password"].value !== "") {
                    checkField(form.elements["confirm_password"], form);
                }
            });
        });

        // Schedule form: ticking or unticking a day checks that day's two time boxes
        Array.prototype.forEach.call(
            form.querySelectorAll('input[type="checkbox"][name^="working_"]'),
            function (box) {
                box.addEventListener("change", function () {
                    var day = box.name.replace("working_", "");
                    ["start_" + day, "end_" + day].forEach(function (timeName) {
                        var timeField = form.elements[timeName];
                        if (timeField) { checkField(timeField, form); }
                    });
                });
            }
        );

        // When the visitor sends the form
        form.addEventListener("submit", function (event) {
            // Another script already stopped it (for example Cancel in a confirm popup)
            if (event.defaultPrevented) {
                return;
            }

            var firstBad = null;
            fields.forEach(function (field) {
                if (!checkField(field, form) && firstBad === null) {
                    firstBad = field;
                }
            });

            if (firstBad) {
                event.preventDefault();   // do not send the form
                firstBad.focus();         // put the cursor in the first wrong box
                return;
            }

            // The form is fine: block a second click on the button.
            // The "0" waits until the browser has collected the form data first.
            var button = event.submitter;
            if (button && !button.name) {
                setTimeout(function () { button.disabled = true; }, 0);
            }
        });
    }


    /* ---------- Start ---------- */

    document.querySelectorAll("form").forEach(function (form) {
        if (form.method.toLowerCase() === "post") {
            enhanceForm(form);
        }
    });

    // If the visitor presses the browser's Back button, give the buttons back
    window.addEventListener("pageshow", function () {
        document.querySelectorAll("button[type='submit']:disabled").forEach(function (button) {
            button.disabled = false;
        });
    });
})();