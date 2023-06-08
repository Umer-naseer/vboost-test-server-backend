django.jQuery(function () {
    var textarea = django.jQuery('textarea')[0];

    // Define an extended mixed-mode that understands vbscript and
    // leaves mustache/handlebars embedded templates in html mode
    var mixed_mode = {
        name: "htmlmixed",
        scriptTypes: [
            {matches: /\/x-handlebars-template|\/x-mustache/i,
                mode: null},
            {matches: /(text|application)\/(x-)?vb(a|script)/i,
                mode: "vbscript"}
        ]
    };

    CodeMirror.defineMode("template", function (config, parserConfig) {
        var overlay = {
            token: function (stream, state) {
                var ch;
                if (stream.match("{{") || stream.match("{%")) {
                    while ((ch = stream.next()) != null)
                        if ((ch == "}" || ch == "%") && stream.next() == "}") break;
                    stream.eat("}");
                    return "jinja2";
                }
                while (stream.next() != null && !stream.match("{{", false) && !stream.match("{%", false)) {
                }
                return null;
            }
        };

        return CodeMirror.overlayMode(
            CodeMirror.getMode(config, parserConfig.backdrop || 'htmlmixed'),
            overlay
        );
    });

    var editor = CodeMirror.fromTextArea(textarea, {
        mode: 'template',
        tabMode: "indent",
        indentUnit: 2,
        tabSize: 2,
        autoFocus: true,
        lineNumbers: true,
        lineWrapping: true,
        extraKeys: {
            Tab: function(cm) {
                var spaces = Array(cm.getOption("indentUnit") + 1).join(" ");
                cm.replaceSelection(spaces, "end", "+input");
            }
        }
    });
});