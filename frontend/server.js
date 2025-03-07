const express = require('express');
const morgan = require("morgan");
const { spawn } = require('child_process');
const cfb = require('./cfb/routes.js');
var path = require('path');
const port = process.env.PORT || 8000;

const util = require('util');
const debuglog = util.debuglog('[frontend]');

const app = express();
app.use(morgan('[frontend] :remote-addr - :remote-user [:date[clf]] ":method :url HTTP/:http-version" :status :res[content-length]'));
app.set('views', path.join(__dirname, 'views'));
app.set('view engine', 'ejs');
app.use(express.static(__dirname + '/public'));
app.use('/cfb', cfb);

// index page
app.get('/', function(req, res) {
    res.redirect('/cfb/');
});

// Start the frontend service
app.listen(port, () => {
    debuglog(`listening on port ${port}`)
})

app.use(function (err, req, res, next) {
    debuglog(err.stack)
    if (req.method == "POST" || req.query.json == true || req.query.json == "true" || req.query.json == "1") {
        return res.status(500).json({
            status: 500,
            message: err.message
        });
    } else {
        return res.status(500).render('error', {
            error: err
        });
    }
})
