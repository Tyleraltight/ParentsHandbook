import asyncio, base64, subprocess

JS = r"""
(function() {
    var result = {};
    var targets = [
        { key: 'Sex & Nudity',       pattern: /sex|nudity/i },
        { key: 'Violence & Gore',    pattern: /violence|gore/i },
        { key: 'Profanity',          pattern: /profanity|language/i },
        { key: 'Frightening Scenes', pattern: /frightening|intense/i }
    ];

    targets.forEach(function(t) { result[t.key] = []; });

    var headers = document.querySelectorAll('h3, h4, [class*="ipc-title__text"]');
    headers.forEach(function(header) {
        var headerText = header.textContent.trim();
        targets.forEach(function(t) {
            if (t.pattern.test(headerText)) {
                var section = header.closest('section');
                if (section) {
                    var items = section.querySelectorAll('.ipc-html-content-inner-div, .ipl-zebra-list__item, li');
                    var texts = Array.from(items).map(i => i.textContent.trim()).filter(txt => txt.length > 5);
                    if (texts.length > 0) {
                        result[t.key].push(texts.join(' \\n '));
                    } else {
                        result[t.key].push(section.innerText);
                    }
                }
            }
        });
    });
    
    var finalResult = {};
    targets.forEach(function(t) {
        var arr = result[t.key];
        var longest = '';
        arr.forEach(function(str) {
            if (str && str.length > longest.length) longest = str;
        });
        finalResult[t.key] = longest;
    });
    return JSON.stringify(finalResult);
})()
"""

b64 = base64.b64encode(JS.encode()).decode()
print('Running agent-browser eval...')
proc = subprocess.run(f'agent-browser eval -b {b64}', capture_output=True, text=True, shell=True)
print('STDOUT:')
print(proc.stdout)
print('STDERR:')
print(proc.stderr)
