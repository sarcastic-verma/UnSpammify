from app import (app, db, render_template, request, session, flash, redirect, sendMail, sort_events)
from forms import AddEvent
from models import EventsModel, UserModel
from random import randint  # generating random id for events
from datetime import datetime, date

URL_PREFIX = '/events'


def get_event_description(e, msg=''):
    m = f""" ♦  {e.EventHeading}


{e.EventDescription}

♦ Date : {e.EventDate}
♦ Time : {e.EventTime}
♦ Venue : {e.EventVenue}
"""
    if msg == '':
        return m
    else:
        return f"####  {msg}  ####\n\n" + m


def generate_random_id(length=6):
    generated_id = "".join([str(randint(1, 9)) for x in range(length)])

    rs = db.session.query(EventsModel.ID).all()
    rs = tuple(x[0] for x in rs)

    while generated_id in rs:
        generated_id = generate_random_id()

    return generated_id


@app.route(URL_PREFIX + '/')
def display_events():
    if 'user' in session or 'admin' in session:  # accessible only if user or admin is logged in
        return render_template("events/homepage.html",
                               events=sort_events(EventsModel.query.all()))
    else:
        flash("Not Logged In", 'danger')
        print("Not Logged In")
        return redirect('/login')


# add new event
@app.route(URL_PREFIX + '/add', methods=['GET', 'POST'])
def add_new_event():
    if 'admin' in session:  # can only add event if any admin is logged in
        form = AddEvent(request.form)
        if request.method == "POST" and form.validate():
            date = datetime.strptime(str(form.date.data), '%Y-%m-%d').strftime('%d/%m/%Y')
            time = str(form.time.data).strip().upper()
            venue = str(form.venue.data).strip().upper()
            heading = str(form.heading.data).strip()
            description = str(form.description.data).strip()

            random_id = generate_random_id()

            # add event to database
            e = EventsModel(random_id, heading, description, date, time, venue)
            db.session.add(e)
            db.session.commit()

            flash(f"Event Added Successfully With ID : '{random_id}'", 'success')
            print(f"Event Added Successfully With ID : '{random_id}'")
    else:
        flash("Admin Not Logged In", 'danger')
        print("Admin Not Logged In")
        return redirect('/login')
    return render_template("events/add-event.html", form=form)


@app.route(URL_PREFIX + '/modify/<string:event_id>', methods=['GET', 'POST'])
def modify_event(event_id):
    if 'admin' in session:
        event = EventsModel.query.filter_by(ID=event_id).first()
        if event is None:  # if event does not exist
            flash(f"Event With ID : '{event_id}' Does Not Exist", 'danger')
            print(f"Event With ID : '{event_id}' Does Not Exist")
            return redirect('/admin')
        else:
            field_values = {
                'date': datetime.strptime(event.EventDate, '%d/%m/%Y').date(),
                'time': event.EventTime,
                'venue': event.EventVenue,
                'heading': event.EventHeading,
                'description': event.EventDescription
            }
            form = AddEvent(request.form, **field_values)  # form is same for add and modify
            if request.method == "POST" and form.validate():

                new_date = datetime.strptime(str(form.date.data), '%Y-%m-%d').strftime('%d/%m/%Y')
                new_time = str(form.time.data).strip().upper()
                new_venue = str(form.venue.data).strip().upper()
                new_heading = str(form.heading.data).strip()
                new_description = str(form.description.data).strip()

                # get all favourite users for <event_id>
                rs = UserModel.query.all()
                recipients = []
                for user in rs:
                    if event_id in user.InterestedActivities:
                        recipients.append(user.ID + '@bennett.edu.in')

                event_modified = False
                # list containing titles of all the changes made to the event ... used in subject for mail
                changes = []

                if new_date != event.EventDate:
                    event.EventDate = new_date
                    event_modified = True
                    changes.append('Date')
                if new_time != event.EventTime:
                    event.EventTime = new_time
                    event_modified = True
                    changes.append('Time')
                if new_venue != event.EventVenue:
                    event.EventVenue = new_venue
                    event_modified = True
                    changes.append('Venue')
                if new_heading != event.EventHeading:
                    event.EventHeading = new_heading
                    event_modified = True
                    changes.append('Heading')
                if new_description != event.EventDescription:
                    event.EventDescription = new_description
                    event_modified = True
                    changes.append('Description')

                if event_modified:
                    msg = " ".join([x for x in changes]) + " Changed"

                    db.session.commit()

                    sendMail(f"Event Modified : {event.EventHeading}",
                             get_event_description(event, msg),
                             recipients,
                             'Email Sent Successfully')

                    flash(f"Event With ID : '{event_id}' Modified Successfully", 'success')
                    print(f"Event With ID : '{event_id}' Modified Successfully")
                else:
                    flash(f"Event With ID : '{event_id}' Not Modified ! All fields are same", 'warning')
                    print(f"Event With ID : '{event_id}' Not Modified ! All fields are same")

                return redirect('/admin')
    else:
        flash("Admin Not Logged In", 'danger')
        print("Admin Not Logged In")
        return redirect('/login')
    return render_template("events/modify-event.html", form=form)


# delete event
@app.route(URL_PREFIX + '/delete/<string:event_id>')
def delete_event(event_id):
    if 'admin' in session:
        # delete event
        e = EventsModel.query.filter_by(ID=event_id).first()
        db.session.delete(e)

        # delete event from user's favourite events
        rs = UserModel.query.all()
        recipients = []
        for user in rs:
            if event_id in user.InterestedActivities:
                recipients.append(user.ID + '@bennett.edu.in')
                fav_events = user.InterestedActivities.replace(event_id + ',', '')
                user.InterestedActivities = fav_events

        sendMail(
            "Event Cancelled : " + e.EventHeading,
            get_event_description(e),
            recipients,
            "Mail Sent Successfully"
        )

        # commit changes
        db.session.commit()

        flash(f"Event With ID : '{event_id}' Deleted Successfully", 'success')
        print(f"Event With ID : '{event_id}' Deleted Successfully")
        return redirect('/admin')
    else:
        flash("Admin Not Logged In", 'danger')
        print("Admin Not Logged In")
        return redirect('/login')


# send reminder for event
@app.route(URL_PREFIX + '/send-reminder/<string:event_id>')
def send_reminder_event(event_id):
    if 'admin' in session:
        event = EventsModel.query.filter_by(ID=event_id).first()
        if event is None:  # if event does not exist
            flash(f"Event With ID : '{event_id}' Does Not Exist", 'danger')
            print(f"Event With ID : '{event_id}' Does Not Exist")
            return redirect('/admin')
        else:
            # get all favourite users for <event_id>
            rs = UserModel.query.all()
            recipients = []
            for user in rs:
                if event_id in user.InterestedActivities:
                    recipients.append(user.ID + '@bennett.edu.in')
            print("Sending Emails ...")
            sendMail("REMINDER : " + event.EventHeading,
                     get_event_description(event),
                     recipients,
                     f'Mail Sent Successfully to {len(recipients)} student(s)')
            return redirect('/admin')
    else:
        flash("Admin Not Logged In", 'danger')
        print("Admin Not Logged In")
        return redirect('/login')


@app.route(URL_PREFIX + '/<string:event_id>')
def display_event(event_id):
    if 'user' in session or 'admin' in session:  # logged in
        e = EventsModel.query.filter_by(ID=event_id).first()
        if e is None:
            flash(f"Event  With ID : '{event_id}' Does Not Exist", 'success')
            print(f"Event  With ID : '{event_id}' Does Not Exist")
            return redirect(URL_PREFIX)
        else:
            users_interested = []
            num_interested = 0
            total_users_registered = 0
            if 'admin' in session:  # if admin in session then show names of interested users
                rs = UserModel.query.all()
                total_users_registered = len(rs)
                for i in rs:
                    if event_id in i.InterestedActivities:
                        users_interested.append([i.ID, i.Name])
                num_interested = len(users_interested)

            return render_template('events/display-event-page.html', event=e,
                                   users_interested=users_interested,
                                   num_interested=num_interested,
                                   total_users_registered=total_users_registered
                                   )
    else:
        flash("Not Logged In", 'danger')
        print("Not Logged In")
        return redirect('/login')


@app.route(URL_PREFIX + '/add-to-fav/<string:event_id>')
def add_event_to_favourites(event_id):
    if 'user' in session:
        rs = UserModel.query.filter_by(ID=session['user']).first()
        if event_id in rs.InterestedActivities:
            flash(f"Event With ID : '{event_id}' Already In {rs.Name}'s Favourites", 'warning')
            print(f"Event With ID : '{event_id}' Already In {rs.Name}'s Favourites")
        else:
            rs.InterestedActivities = rs.InterestedActivities + event_id + ','
            db.session.commit()
            flash(f"Event With ID : '{event_id}' Added To {rs.Name}'s Favourites", 'success')
            print(f"Event With ID : '{event_id}' Added To {rs.Name}'s Favourites")
        return redirect('/events')
    else:
        flash("User Not Logged In", 'danger')
        print("User Not Logged In")
        return redirect('/login')


@app.route(URL_PREFIX + '/delete-old-events')
def delete_old_events():
    if 'admin' in session:
        current_date = date.today()
        events = EventsModel.query.all()
        num_events = 0  # total number of events deleted
        for e in events:
            event_date = datetime.strptime(e.EventDate, '%d/%m/%Y').date()
            if event_date < current_date:
                num_events += 1
                db.session.delete(e)
            db.session.commit()

        if num_events:
            flash(f"Deleted {num_events} Old Events Successfully", 'success')
            print(f"Deleted {num_events} Old Events Successfully")
        else:
            flash("No Old Events Exist [Date Wise]", 'success')
            print("No Old Events Exist [Date Wise]")
        return redirect('/admin')
    else:
        flash("Admin Not Logged In", 'danger')
        print("Admin Not Logged In")
        return redirect('/login')


@app.route(URL_PREFIX + '/remove-from-fav/<string:event_id>')
def remove_event_from_favourites(event_id):
    if 'user' in session:
        rs = UserModel.query.filter_by(ID=session['user']).first()
        if event_id in rs.InterestedActivities:
            rs.InterestedActivities = str(rs.InterestedActivities).replace(event_id + ',', '')
            db.session.commit()
            flash(f"Event With ID : '{event_id}' Removed From {rs.Name}'s Favourites", 'success')
            print(f"Event With ID : '{event_id}' Removed From {rs.Name}'s Favourites")
        else:
            flash(f"Event With ID : '{event_id}' Not in {rs.Name}'s Favourites", 'danger')
            print(f"Event With ID : '{event_id}' Not in {rs.Name}'s Favourites")
        return redirect('/user/' + session['user'])
    else:
        flash("User Not Logged In", 'danger')
        print("User Not Logged In")
        return redirect('/login')
