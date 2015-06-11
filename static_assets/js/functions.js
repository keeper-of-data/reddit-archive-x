function htmlDecode(input){
    // Taken from https://css-tricks.com/snippets/javascript/unescape-html-in-js/
    var e = document.createElement('div');
    e.innerHTML = input;
    return e.childNodes.length === 0 ? "" : e.childNodes[0].nodeValue;
} //END htmlDecode()

function getJson(json_file){
    var $json_query = $.getJSON( json_file );
    return $json_query;
} //END getJson()